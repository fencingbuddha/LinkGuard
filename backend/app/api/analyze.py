from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import OrgContext, require_api_key

router = APIRouter()


class AnalyzeUrlIn(BaseModel):
    url: str


@router.post("/api/analyze-url")
def analyze_url(payload: AnalyzeUrlIn, ctx: OrgContext = Depends(require_api_key)):
    # Placeholder response for Sprint 1
    return {
        "url": payload.url,
        "org_id": ctx.org_id,
        "verdict": "unknown",
        "reasons": [],
    }