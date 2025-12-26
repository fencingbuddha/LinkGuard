from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, verify_password, hash_password, decode_access_token
from app.db import get_db
from app.models.admin_user import AdminUser
from app.models.organization import Organization


router = APIRouter(prefix="/api/admin", tags=["admin"])

_auth_scheme = HTTPBearer(auto_error=False)


def _raise_unauthorized(detail: str) -> None:
    # Standard header helps browsers/clients understand Bearer auth.
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_auth_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not creds or creds.scheme.lower() != "bearer":
        _raise_unauthorized("Missing bearer token")

    try:
        payload = decode_access_token(creds.credentials)
    except Exception:
        _raise_unauthorized("Invalid token")

    if not payload or payload.get("type") != "admin":
        _raise_unauthorized("Invalid token")

    sub = payload.get("sub")
    try:
        admin_id = int(sub)
    except Exception:
        _raise_unauthorized("Invalid token")

    user = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not user or not user.is_active:
        _raise_unauthorized("Invalid token")

    return user


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminBootstrapIn(BaseModel):
    org_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)



class AdminBootstrapOut(TokenOut):
    admin_id: int
    org_id: int


class AdminChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminMeOut(BaseModel):
    admin_id: int
    email: EmailStr
    is_active: bool
    created_at: datetime


@router.get("/me", response_model=AdminMeOut)
def admin_me(user: AdminUser = Depends(require_admin_user)) -> AdminMeOut:
    created_at = user.created_at
    # SQLite can sometimes yield strings for timestamps depending on model/type; normalize.
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    return AdminMeOut(
        admin_id=user.id,
        email=user.email,
        is_active=bool(user.is_active),
        created_at=created_at,
    )


@router.get("/health")
def admin_health(user: AdminUser = Depends(require_admin_user)) -> dict:
    # If the token is valid, this returns 200; otherwise require_admin_user raises 401.
    return {"ok": True, "admin_id": user.id}


@router.post("/login", response_model=TokenOut)
def admin_login(payload: AdminLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.strip().lower()
    user = db.query(AdminUser).filter(AdminUser.email == email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        _raise_unauthorized("Invalid credentials")

    if not user.is_active:
        _raise_unauthorized("Inactive user")

    # deps.py expects payload["type"] == "admin" (create_access_token should include it)
    token = create_access_token(sub=str(user.id))
    return TokenOut(access_token=token)


@router.post("/bootstrap", response_model=AdminBootstrapOut)
def bootstrap_admin(
    payload: AdminBootstrapIn,
    db: Session = Depends(get_db),
    x_bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> AdminBootstrapOut:
    # Never allow bootstrap in production
    env = os.getenv("ENV", "dev").lower()
    if env in {"prod", "production"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Require a bootstrap secret in non-prod
    expected = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")
    if not expected or x_bootstrap_token != expected:
        _raise_unauthorized("Invalid bootstrap token")

    # Only allow bootstrap when there are zero admins
    if db.query(AdminUser).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap already completed",
        )

    # Create (or reuse) organization
    org_name = payload.org_name.strip()
    org = db.query(Organization).filter(Organization.name == org_name).first()
    if org is None:
        org = Organization(name=org_name)
        db.add(org)
        db.flush()  # assign org.id

    # Create first admin
    email = payload.email.strip().lower()
    user = AdminUser(
        email=email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()  # assign user.id

    token = create_access_token(sub=str(user.id))
    db.commit()

    return AdminBootstrapOut(access_token=token, admin_id=user.id, org_id=org.id)


@router.post("/change-password")
def change_password(
    payload: AdminChangePasswordIn,
    user: AdminUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        _raise_unauthorized("Invalid credentials")

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()

    return {"ok": True}