import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from urllib.parse import parse_qs, urlparse

from app.db import SessionLocal
from app.models.scan_event import RiskCategory, ScanEvent

from app.api.deps import OrgContext, require_api_key, rate_limit_analyze_url
from app.services.url_analysis import analyze_url as analyze_url_service

router = APIRouter()

logger = logging.getLogger("linkguard.analyze")


def _record_scan_event(*, org_id: int, normalized_url: str, risk_category: str) -> None:
    """Best-effort persistence of ScanEvent for admin analytics.

    This should never break the analyze endpoint; failures are swallowed.
    """
    try:
        host = urlparse(normalized_url or "").netloc or ""
        # Strip port if present (e.g., example.com:443)
        domain = host.split(":", 1)[0] if host else "unknown"

        # Normalize to enum
        rc = (risk_category or "").upper()
        if rc not in {"SAFE", "SUSPICIOUS", "DANGEROUS"}:
            rc = "SUSPICIOUS"  # conservative default

        s = SessionLocal()
        try:
            s.add(
                ScanEvent(
                    org_id=org_id,
                    domain=domain,
                    risk_category=RiskCategory(rc),
                )
            )
            s.commit()
        finally:
            s.close()
    except Exception:
        # Intentionally ignore to keep /api/analyze-url reliable.
        return


class AnalyzeUrlIn(BaseModel):
    url: str


class AnalyzeUrlOut(BaseModel):
    org_id: int
    request_id: str

    # Demo-friendly stable contract
    category: str
    score: int
    explanation: str

    # Compatibility fields (kept for extension/dashboard)
    risk_category: str
    explanations: List[str]
    normalized_url: str


# --- Email scan models ---

class AnalyzeEmailIn(BaseModel):
    # MVP: links-only. Sender/body can be added later.
    links: List[str]
    source: Optional[str] = None


class AnalyzeEmailLinkOut(BaseModel):
    url: str
    normalized_url: str

    # Demo-friendly stable contract
    category: str
    score: int
    explanation: str

    # Compatibility fields
    risk_category: str
    explanations: List[str]


class AnalyzeEmailOut(BaseModel):
    org_id: int
    request_id: str

    # Overall verdict for the email scan (derived from worst link)
    category: str
    score: int
    explanation: str

    # Compatibility fields
    risk_category: str
    explanations: List[str]

    # Per-link results
    links: List[AnalyzeEmailLinkOut]


@router.post("/api/analyze-url", response_model=AnalyzeUrlOut, dependencies=[Depends(rate_limit_analyze_url)])
def analyze_url_endpoint(payload: AnalyzeUrlIn, ctx: OrgContext = Depends(require_api_key)):
    request_id = str(uuid4())
    started = time.perf_counter()

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    # Dev-only test hook: force specific categories using a query param.
    # Examples:
    #   https://example.com/?linkguard_test=suspicious
    #   https://example.com/?linkguard_test=danger
    try:
        qs = parse_qs(urlparse(url).query)
        test_flag = (qs.get("linkguard_test", [""])[0] or "").lower()
    except Exception:
        test_flag = ""

    if test_flag in {"danger", "dangerous"}:
        service_result = {
            "risk_category": "DANGEROUS",
            "score": 100,
            "explanations": ["Forced DANGEROUS via linkguard_test (dev hook)."],
            "normalized_url": url,
        }
    elif test_flag in {"suspicious", "sus"}:
        service_result = {
            "risk_category": "SUSPICIOUS",
            "score": 60,
            "explanations": ["Forced SUSPICIOUS via linkguard_test (dev hook)."],
            "normalized_url": url,
        }
    else:
        # Real analysis (must never crash the demo)
        try:
            service_result = analyze_url_service(url) or {}
        except Exception:
            logger.exception(
                "analyze_url_service failed",
                extra={"request_id": request_id, "org_id": ctx.org_id},
            )
            service_result = {
                "risk_category": "SUSPICIOUS",
                "score": 50,
                "explanations": ["Analysis temporarily unavailable; proceed with caution."],
                "normalized_url": url,
            }

    risk_category = (service_result.get("risk_category") or "SUSPICIOUS").upper()
    if risk_category not in {"SAFE", "SUSPICIOUS", "DANGEROUS"}:
        risk_category = "SUSPICIOUS"

    score = int(service_result.get("score") or 0)

    explanations = service_result.get("explanations") or []
    if not isinstance(explanations, list):
        explanations = [str(explanations)]

    explanation = "; ".join([str(x) for x in explanations if x]) or "No explanation available."
    normalized_url = service_result.get("normalized_url") or url

    # Best-effort event logging (should never break endpoint)
    _record_scan_event(
        org_id=ctx.org_id,
        normalized_url=normalized_url,
        risk_category=risk_category,
    )

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "analyze_url",
        extra={
            "request_id": request_id,
            "org_id": ctx.org_id,
            "risk_category": risk_category,
            "latency_ms": latency_ms,
        },
    )

    return {
        "org_id": ctx.org_id,
        "request_id": request_id,

        # Demo-friendly stable fields
        "category": risk_category,
        "score": score,
        "explanation": explanation,

        # Compatibility fields
        "risk_category": risk_category,
        "explanations": explanations,
        "normalized_url": normalized_url,
    }


# --- Email scan endpoint (links-only MVP) ---

@router.post(
    "/api/analyze-email",
    response_model=AnalyzeEmailOut,
    dependencies=[Depends(rate_limit_analyze_url)],
)
def analyze_email_endpoint(payload: AnalyzeEmailIn, ctx: OrgContext = Depends(require_api_key)):
    """Analyze an email context using a list of extracted links (MVP).

    Outlook (and later mobile) can extract links client-side and send them here.
    Sender/body analysis can be added later without breaking this contract.
    """
    request_id = str(uuid4())
    started = time.perf_counter()

    links_in = payload.links or []
    if not isinstance(links_in, list) or len(links_in) == 0:
        raise HTTPException(status_code=400, detail="links is required")

    # Helper to rank severity deterministically
    severity_rank = {"SAFE": 0, "SUSPICIOUS": 1, "DANGEROUS": 2}

    per_link: List[Dict[str, Any]] = []
    overall_rc = "SAFE"
    overall_score = 0
    overall_explanations: List[str] = []

    for raw_url in links_in:
        url = (str(raw_url) or "").strip()
        if not url:
            continue

        # Reuse the same dev hook behavior as /api/analyze-url
        try:
            qs = parse_qs(urlparse(url).query)
            test_flag = (qs.get("linkguard_test", [""])[0] or "").lower()
        except Exception:
            test_flag = ""

        if test_flag in {"danger", "dangerous"}:
            service_result = {
                "risk_category": "DANGEROUS",
                "score": 100,
                "explanations": ["Forced DANGEROUS via linkguard_test (dev hook)."],
                "normalized_url": url,
            }
        elif test_flag in {"suspicious", "sus"}:
            service_result = {
                "risk_category": "SUSPICIOUS",
                "score": 60,
                "explanations": ["Forced SUSPICIOUS via linkguard_test (dev hook)."],
                "normalized_url": url,
            }
        else:
            try:
                service_result = analyze_url_service(url) or {}
            except Exception:
                logger.exception(
                    "analyze_url_service failed (email)",
                    extra={"request_id": request_id, "org_id": ctx.org_id},
                )
                service_result = {
                    "risk_category": "SUSPICIOUS",
                    "score": 50,
                    "explanations": ["Analysis temporarily unavailable; proceed with caution."],
                    "normalized_url": url,
                }

        risk_category = (service_result.get("risk_category") or "SUSPICIOUS").upper()
        if risk_category not in {"SAFE", "SUSPICIOUS", "DANGEROUS"}:
            risk_category = "SUSPICIOUS"

        score = int(service_result.get("score") or 0)

        explanations = service_result.get("explanations") or []
        if not isinstance(explanations, list):
            explanations = [str(explanations)]

        explanation = "; ".join([str(x) for x in explanations if x]) or "No explanation available."
        normalized_url = service_result.get("normalized_url") or url

        # Best-effort event logging per link
        _record_scan_event(org_id=ctx.org_id, normalized_url=normalized_url, risk_category=risk_category)

        per_link.append(
            {
                "url": url,
                "normalized_url": normalized_url,
                "category": risk_category,
                "score": score,
                "explanation": explanation,
                "risk_category": risk_category,
                "explanations": explanations,
            }
        )

        # Overall = worst link by severity, then score
        if severity_rank.get(risk_category, 1) > severity_rank.get(overall_rc, 0):
            overall_rc = risk_category
            overall_score = score
        elif risk_category == overall_rc and score > overall_score:
            overall_score = score

        if risk_category != "SAFE" and explanations:
            overall_explanations.append(str(explanations[0]))

    if not per_link:
        raise HTTPException(status_code=400, detail="links must include at least one non-empty url")

    if not overall_explanations:
        overall_explanations = ["No suspicious links detected."]

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "analyze_email",
        extra={
            "request_id": request_id,
            "org_id": ctx.org_id,
            "risk_category": overall_rc,
            "latency_ms": latency_ms,
            "link_count": len(per_link),
            "source": payload.source or "",
        },
    )

    return {
        "org_id": ctx.org_id,
        "request_id": request_id,
        "category": overall_rc,
        "score": overall_score,
        "explanation": str(overall_explanations[0]),
        "risk_category": overall_rc,
        "explanations": overall_explanations[:3],
        "links": per_link,
    }