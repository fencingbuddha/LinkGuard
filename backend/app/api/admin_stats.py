from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.organization import Organization
from app.models.scan_event import RiskCategory, ScanEvent

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _default_date_range() -> tuple[date, date]:
    today = date.today()
    return (today - timedelta(days=13), today)  # last 14 days inclusive


def _resolve_org_id(db: Session, org_id_raw: str) -> int:
    # If org_id is numeric, treat it as Organization.id
    if org_id_raw.isdigit():
        org = db.query(Organization).filter(Organization.id == int(org_id_raw)).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org.id

    # Otherwise try Organization.slug (if present), else Organization.name (if present)
    filters = []
    if hasattr(Organization, "slug"):
        filters.append(getattr(Organization, "slug") == org_id_raw)
    if hasattr(Organization, "name"):
        filters.append(getattr(Organization, "name") == org_id_raw)

    if not filters:
        raise HTTPException(status_code=400, detail="Organization identifier not supported")

    org = db.query(Organization).filter(or_(*filters)).first()  # type: ignore[name-defined]
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org.id


@router.get("/stats")
def get_admin_stats(
    org_id: str = Query(..., description="Organization id or slug/name"),
    from_: date | None = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    # Default date range
    if from_ is None or to is None:
        d_from, d_to = _default_date_range()
        from_ = from_ or d_from
        to = to or d_to

    # Convert to datetimes (inclusive end of day)
    start_dt = datetime.combine(from_, datetime.min.time())
    end_dt = datetime.combine(to, datetime.max.time())

    # Resolve org_id string -> int FK
    org_pk = _resolve_org_id(db, org_id)

    base_filters = [
        ScanEvent.org_id == org_pk,
        ScanEvent.timestamp >= start_dt,
        ScanEvent.timestamp <= end_dt,
    ]

    # total_scans
    total_scans = (
        db.query(func.count(ScanEvent.id))
        .filter(*base_filters)
        .scalar()
        or 0
    )

    # risk_distribution
    risk_distribution = {
        "SAFE": 0,
        "SUSPICIOUS": 0,
        "DANGEROUS": 0,
    }

    risk_rows = (
        db.query(ScanEvent.risk_category, func.count(ScanEvent.id))
        .filter(*base_filters)
        .group_by(ScanEvent.risk_category)
        .all()
    )
    for risk, cnt in risk_rows:
        key = risk.value if hasattr(risk, "value") else str(risk)
        if key in risk_distribution:
            risk_distribution[key] = int(cnt)

    # top_risky_domains (SUSPICIOUS + DANGEROUS)
    top_risky_rows = (
        db.query(ScanEvent.domain, func.count(ScanEvent.id).label("cnt"))
        .filter(*base_filters)
        .filter(ScanEvent.risk_category.in_([RiskCategory.SUSPICIOUS, RiskCategory.DANGEROUS]))
        .group_by(ScanEvent.domain)
        .order_by(desc("cnt"))
        .limit(10)
        .all()
    )
    top_risky_domains = [{"domain": d, "count": int(cnt)} for d, cnt in top_risky_rows]

    # daily_scan_trend (SQLite-friendly)
    daily_rows = (
        db.query(func.date(ScanEvent.timestamp).label("d"), func.count(ScanEvent.id).label("cnt"))
        .filter(*base_filters)
        .group_by("d")
        .order_by("d")
        .all()
    )
    daily_scan_trend = [{"date": str(d), "count": int(cnt)} for d, cnt in daily_rows]

    return {
        "total_scans": int(total_scans),
        "risk_distribution": risk_distribution,
        "top_risky_domains": top_risky_domains,
        "daily_scan_trend": daily_scan_trend,
    }