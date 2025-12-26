import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
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