"""Dev helper: ensure a known API key exists for local testing.

Security note:
- Do NOT print plaintext API keys to stdout.
- This script prints only a masked representation and the key prefix.
"""

from __future__ import annotations

import hashlib
import os

_API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", "dev-pepper-change-me")

from app.db import SessionLocal
from app.models.api_key import ApiKey


def _hash_api_key(raw_key: str) -> str:
    """Hash API key using the same peppered scheme as require_api_key()."""
    data = (_API_KEY_PEPPER + raw_key).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _mask(key: str) -> str:
    if not key or len(key) < 12:
        return "****"
    return f"{key[:6]}…{key[-4:]}"


def main() -> None:
    raw_key = os.getenv("DEV_API_KEY", "dev-key-123")  # dev-only default
    org_id = int(os.getenv("DEV_ORG_ID", "1"))

    key_hash = _hash_api_key(raw_key)
    key_prefix = raw_key[:8]

    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if existing:
            existing.org_id = org_id
            existing.is_active = True
            existing.revoked_at = None
            existing.key_prefix = key_prefix
            db.commit()
            print(f"Updated API key: {_mask(raw_key)} (prefix={key_prefix}, org_id={org_id})")
            return

        db.add(
            ApiKey(
                org_id=org_id,
                key_hash=key_hash,
                key_prefix=key_prefix,
                is_active=True,
                revoked_at=None,
            )
        )
        db.commit()
        print(f"Created API key: {_mask(raw_key)} (prefix={key_prefix}, org_id={org_id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()