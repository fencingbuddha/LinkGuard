from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, require_admin
from app.db import get_db
from app.models.organization import Organization

router = APIRouter(prefix="/api/admin/orgs", tags=["admin-orgs"])


class OrgOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class OrgCreateIn(BaseModel):
    name: str


@router.get("", response_model=list[OrgOut])
def list_orgs(
    _: AdminContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Organization]:
    return db.query(Organization).order_by(Organization.id.asc()).all()


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: OrgCreateIn,
    _: AdminContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Organization:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Organization name is required")

    existing = db.query(Organization).filter(Organization.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Organization already exists")

    org = Organization(name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org