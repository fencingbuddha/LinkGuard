from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, verify_password
from app.db import get_db
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenOut)
def admin_login(payload: AdminLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.strip().lower()
    user = db.query(AdminUser).filter(AdminUser.email == email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    token = create_access_token(sub=str(user.id))
    return TokenOut(access_token=token)