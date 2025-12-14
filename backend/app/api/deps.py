from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.api_key import ApiKey, ApiKeyStatus


@dataclass(frozen=True)
class OrgContext:
    org_id: int
    api_key_id: int


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