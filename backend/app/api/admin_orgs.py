from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import secrets

from app.api.deps import AdminContext, require_admin
from app.db import get_db
from app.models.api_key import ApiKey
from app.models.organization import Organization

router = APIRouter(prefix="/api/admin", tags=["admin"])


class OrgOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class OrgCreateIn(BaseModel):
    name: str


class ApiKeyCreateOut(BaseModel):
    id: int
    org_id: int
    api_key: str  # returned once
    key_prefix: str


class ApiKeyRevokeOut(BaseModel):
    id: int
    revoked: bool


@router.get("/orgs", response_model=list[OrgOut])
def list_orgs(
    _: AdminContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Organization]:
    return db.query(Organization).order_by(Organization.id.asc()).all()


def _generate_raw_api_key() -> str:
    return secrets.token_urlsafe(32)


@router.post("/orgs", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
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


@router.post("/orgs/{org_id}/keys", response_model=ApiKeyCreateOut, status_code=status.HTTP_201_CREATED)
def create_org_key(
    org_id: int,
    _: AdminContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiKeyCreateOut:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    raw_key = _generate_raw_api_key()
    key_prefix = raw_key[:8]

    # Store ONLY a hash of the raw key. Hashing uses the same helper as require_api_key.
    # We re-use deps._hash_api_key to ensure consistency.
    from app.api.deps import _hash_api_key  # local import to avoid cycles

    key_hash = _hash_api_key(raw_key)

    row = ApiKey(
        org_id=org_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return ApiKeyCreateOut(id=row.id, org_id=row.org_id, api_key=raw_key, key_prefix=row.key_prefix)


@router.post("/api-keys/{api_key_id}/revoke", response_model=ApiKeyRevokeOut)
def revoke_api_key(
    api_key_id: int,
    _: AdminContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiKeyRevokeOut:
    row = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    row.is_active = False
    db.commit()

    return ApiKeyRevokeOut(id=row.id, revoked=True)