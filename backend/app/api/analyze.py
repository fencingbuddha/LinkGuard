from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from urllib.parse import parse_qs, urlparse

from app.api.deps import OrgContext, require_api_key
from app.services.url_analysis import analyze_url as analyze_url_service

router = APIRouter()


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
        return {"org_id": ctx.org_id, **result}

    if test_flag in {"suspicious", "sus"}:
        result = {
            "risk_category": "SUSPICIOUS",
            "score": 60,
            "explanations": ["Forced SUSPICIOUS via linkguard_test (dev hook)."],
            "normalized_url": url,
        }
        return {"org_id": ctx.org_id, **result}

    result = analyze_url_service(url)

    return {"org_id": ctx.org_id, **result}