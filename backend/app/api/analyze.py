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
from app.services.sender_analysis import analyze_sender

router = APIRouter()

logger = logging.getLogger("linkguard.analyze")


def _record_scan_event(
    *,
    org_id: int,
    normalized_url: str,
    risk_category: str,
    request_id: str | None = None,
    source: str | None = None,
    scan_type: str | None = None,
    artifact: str | None = None,
) -> None:
    """Best-effort persistence of ScanEvent for admin analytics.

    This should never break the analyze endpoint; failures are swallowed.
    """
    try:
        parsed = urlparse(normalized_url or "")

        domain = "unknown"
        if parsed.scheme == "mailto":
            # mailto:user@domain.com -> domain.com
            addr = (parsed.path or "").strip()
            if "@" in addr:
                domain = addr.split("@", 1)[1].lower() or "unknown"
        else:
            host = parsed.netloc or ""
            # Strip port if present (e.g., example.com:443)
            domain = host.split(":", 1)[0].lower() if host else "unknown"

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
                    request_id=request_id,
                    source=source,
                    scan_type=scan_type,
                    artifact=artifact or normalized_url,
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


class AnalyzeSenderOut(BaseModel):
    score: int
    risk_category: str
    explanations: List[str]
    signals: List[str]


class AnalyzeEmailIn(BaseModel):
    # Links-only still works; sender fields are optional for Outlook integration.
    links: List[str]
    source: Optional[str] = None

    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to_emails: Optional[List[str]] = None


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

    # Overall verdict for the email scan (derived from sender + links)
    category: str
    score: int
    explanation: str

    # Compatibility fields
    risk_category: str
    explanations: List[str]

    # Sender verdict
    sender: AnalyzeSenderOut

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
            "score": 55,
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
        request_id=request_id,
        source="api_analyze_url",
        scan_type="url",
        artifact=normalized_url,
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

    # Sender analysis (optional fields; defaults to SAFE when absent)
    sender_res = analyze_sender(
        from_name=payload.from_name,
        from_email=payload.from_email,
        reply_to_emails=payload.reply_to_emails or [],
    )
    sender_score = int(sender_res.get("score") or 0)
    sender_rc = (sender_res.get("risk_category") or "SAFE").upper()
    sender_explanations = sender_res.get("explanations") or []
    sender_signals = sender_res.get("signals") or []

    if payload.from_email:
        _record_scan_event(
            org_id=ctx.org_id,
            normalized_url=f"mailto:{payload.from_email}",
            risk_category=sender_rc,
            request_id=request_id,
            source=payload.source,
            scan_type="email_sender",
            artifact=payload.from_email,
        )

    per_link: List[Dict[str, Any]] = []

    highest_link_score = 0
    risky_links_count = 0
    dangerous_links_count = 0

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
                "score": 55,
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
        _record_scan_event(
            org_id=ctx.org_id,
            normalized_url=normalized_url,
            risk_category=risk_category,
            request_id=request_id,
            source=payload.source,
            scan_type="email_link",
            artifact=normalized_url,
        )

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

        # Track worst link score and risky link counts
        if score > highest_link_score:
            highest_link_score = score

        if risk_category == "DANGEROUS":
            dangerous_links_count += 1
            risky_links_count += 1
        elif risk_category == "SUSPICIOUS":
            risky_links_count += 1

    if not per_link:
        raise HTTPException(status_code=400, detail="links must include at least one non-empty url")

    # Unified verdict (Acceptance Criteria)
    overall_score = max(sender_score, highest_link_score)

    if overall_score >= 60:
        overall_rc = "DANGEROUS"
    elif overall_score >= 25:
        overall_rc = "SUSPICIOUS"
    else:
        overall_rc = "SAFE"

    # Overall explanations: summarize top sender risks + risky link counts
    overall_explanations: List[str] = []

    if sender_explanations:
        overall_explanations.append(str(sender_explanations[0]))

    if risky_links_count > 0:
        if dangerous_links_count > 0:
            overall_explanations.append(
                f"{dangerous_links_count} dangerous link(s) and {risky_links_count - dangerous_links_count} suspicious link(s) detected."
            )
        else:
            overall_explanations.append(f"{risky_links_count} suspicious link(s) detected.")
    else:
        overall_explanations.append("No suspicious links detected.")

    # Fallback guard
    if not overall_explanations:
        overall_explanations = ["No suspicious signals detected."]

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
            "sender_score": sender_score,
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
        "sender": {
            "score": sender_score,
            "risk_category": sender_rc,
            "explanations": sender_explanations,
            "signals": sender_signals,
        },
        "links": per_link,
    }