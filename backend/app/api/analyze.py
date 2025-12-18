from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from urllib.parse import parse_qs, urlparse

from app.db import SessionLocal
from app.models.scan_event import RiskCategory, ScanEvent

from app.api.deps import OrgContext, require_api_key
from app.services.url_analysis import analyze_url as analyze_url_service

router = APIRouter()


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


@router.post("/api/analyze-url")
def analyze_url_endpoint(payload: AnalyzeUrlIn, ctx: OrgContext = Depends(require_api_key)):
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
        result = {
            "risk_category": "DANGEROUS",
            "score": 100,
            "explanations": ["Forced DANGEROUS via linkguard_test (dev hook)."],
            "normalized_url": url,
        }
        _record_scan_event(org_id=ctx.org_id, normalized_url=result.get("normalized_url", url), risk_category=result.get("risk_category", ""))
        return {"org_id": ctx.org_id, **result}

    if test_flag in {"suspicious", "sus"}:
        result = {
            "risk_category": "SUSPICIOUS",
            "score": 60,
            "explanations": ["Forced SUSPICIOUS via linkguard_test (dev hook)."],
            "normalized_url": url,
        }
        _record_scan_event(org_id=ctx.org_id, normalized_url=result.get("normalized_url", url), risk_category=result.get("risk_category", ""))
        return {"org_id": ctx.org_id, **result}

    result = analyze_url_service(url)
    _record_scan_event(org_id=ctx.org_id, normalized_url=result.get("normalized_url", url), risk_category=result.get("risk_category", ""))

    return {"org_id": ctx.org_id, **result}