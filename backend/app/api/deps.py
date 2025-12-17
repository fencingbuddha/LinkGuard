from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.security import decode_access_token
from app.models.admin_user import AdminUser
from app.models.api_key import ApiKey, ApiKeyStatus


@dataclass(frozen=True)
class OrgContext:
    org_id: int
    api_key_id: int


@dataclass(frozen=True)
class AdminContext:
    admin_user_id: int


bearer_scheme = HTTPBearer(auto_error=False)


def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> OrgContext:
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key == x_api_key.strip())
        .first()
    )

    if not api_key or api_key.status != ApiKeyStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return OrgContext(org_id=api_key.org_id, api_key_id=api_key.id)


def require_admin(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminContext:
    """Require a valid admin JWT in the Authorization: Bearer <token> header."""
    if not creds or not creds.credentials or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # We encode admin tokens with type='admin' in security.py
    if payload.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token required",
        )

    sub = payload.get("sub")
    try:
        admin_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return AdminContext(admin_user_id=admin.id)