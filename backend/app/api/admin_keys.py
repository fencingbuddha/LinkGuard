from __future__ import annotations

import os
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.organization import Organization
from app.models.api_key import ApiKey
from app.models.admin_user import AdminUser
from app.auth.security import decode_access_token


router = APIRouter(prefix="/api/admin", tags=["admin-keys"])


# --- helpers ---

API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", "dev-pepper-change-me")


def _hash_api_key(raw_key: str) -> str:
    # store only a hash; never store plaintext
    data = (API_KEY_PEPPER + raw_key).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def require_admin(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    admin_id = payload.get("sub")
    admin = db.query(AdminUser).filter(AdminUser.id == int(admin_id)).first() if admin_id else None
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return admin


# --- schemas ---

class ApiKeyOut(BaseModel):
    id: int
    org_id: int
    api_key: str  # returned ONCE at creation time
    created_at: datetime


class ApiKeyRevokeOut(BaseModel):
    id: int
    revoked: bool
    revoked_at: datetime


# --- routes ---

@router.post("/orgs/{org_id}/keys", response_model=ApiKeyOut)
def create_org_key(
    org_id: int,
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiKeyOut:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    raw_key = secrets.token_urlsafe(32)  # plaintext returned once
    key_hash = _hash_api_key(raw_key)
    prefix = raw_key[:8]

    row = ApiKey(
        org_id=org_id,
        key_hash=key_hash,
        key_prefix=prefix,
        is_active=True,
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return ApiKeyOut(id=row.id, org_id=row.org_id, api_key=raw_key, created_at=row.created_at)


@router.post("/api-keys/{api_key_id}/revoke", response_model=ApiKeyRevokeOut)
def revoke_key(
    api_key_id: int,
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiKeyRevokeOut:
    row = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    row.is_active = False
    row.revoked_at = _now()
    db.commit()

    return ApiKeyRevokeOut(id=row.id, revoked=True, revoked_at=row.revoked_at)