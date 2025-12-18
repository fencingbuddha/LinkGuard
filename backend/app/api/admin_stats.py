from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/stats")
def get_admin_stats(
    org_id: str = Query(..., description="Organization identifier"),
    from_: date | None = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    # MVP stub: returns a stable shape the frontend can render.
    return {
        "total_scans": 0,
        "risk_distribution": {"SAFE": 0, "SUSPICIOUS": 0, "DANGEROUS": 0},
        "top_risky_domains": [],
        "daily_scan_trend": [],
    }