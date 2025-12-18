from __future__ import annotations

from dataclasses import dataclass
from typing import Deque, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.security import decode_access_token
from app.models.admin_user import AdminUser
from app.models.api_key import ApiKey

import hashlib
import os
import time
from collections import deque


@dataclass(frozen=True)
class OrgContext:
    org_id: int
    api_key_id: int


@dataclass(frozen=True)
class AdminContext:
    admin_user_id: int


bearer_scheme = HTTPBearer(auto_error=False)


_API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", "dev-pepper-change-me")


def _hash_api_key(raw_key: str) -> str:
    data = (_API_KEY_PEPPER + raw_key).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> OrgContext:
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    raw = x_api_key.strip()
    api_key_hash = _hash_api_key(raw)

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == api_key_hash)
        .first()
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Support both the newer schema (is_active/revoked_at) and older schema (status).
    is_active = getattr(api_key, "is_active", None)
    revoked_at = getattr(api_key, "revoked_at", None)
    status_val = getattr(api_key, "status", None)

    if is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if isinstance(status_val, str) and status_val.strip():
        if status_val.strip().upper() != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

    return OrgContext(org_id=api_key.org_id, api_key_id=api_key.id)


# ---- Rate limiting (MVP: in-memory fixed window) ----
# Defaults are intentionally conservative for local dev; override via env.
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "30"))
RATE_LIMIT_WINDOW_S = int(os.getenv("RATE_LIMIT_WINDOW_S", "60"))

# key -> deque of request timestamps (seconds)
_RATE_BUCKETS: Dict[str, Deque[float]] = {}


def _rate_limit_key(ctx: OrgContext, request: Request) -> str:
    """Compute the limiter key.

    MVP: limit per API key id. If for some reason ctx is unavailable, fall back
    to client IP.
    """
    if getattr(ctx, "api_key_id", None):
        return f"api_key:{ctx.api_key_id}"
    client_host = getattr(getattr(request, "client", None), "host", None) or "unknown"
    return f"ip:{client_host}"


def rate_limit_analyze_url(
    request: Request,
    ctx: OrgContext = Depends(require_api_key),
) -> None:
    """Rate limit dependency for /api/analyze-url.

    Uses an in-memory fixed window (sliding by timestamp eviction).
    Returns 429 with Retry-After when exceeded.

    NOTE: This is per-process; production should move to Redis or similar.
    """
    now = time.time()

    key = _rate_limit_key(ctx, request)
    bucket = _RATE_BUCKETS.get(key)
    if bucket is None:
        bucket = deque()
        _RATE_BUCKETS[key] = bucket

    cutoff = now - RATE_LIMIT_WINDOW_S
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_MAX:
        # Earliest timestamp still in window determines when quota frees up.
        retry_after = int((bucket[0] + RATE_LIMIT_WINDOW_S) - now) if bucket else RATE_LIMIT_WINDOW_S
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(retry_after, 1))},
        )

    bucket.append(now)


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

    try:
        payload = decode_access_token(creds.credentials)
    except Exception:
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