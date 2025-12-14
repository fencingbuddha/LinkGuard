from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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

    result = analyze_url_service(url)

    # Include org context so the caller can correlate results.
    return {
        "org_id": ctx.org_id,
        **result,
    }