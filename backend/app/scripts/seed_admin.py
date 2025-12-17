from __future__ import annotations

import os

from app.db import SessionLocal
from app.models.admin_user import AdminUser
from app.auth.security import hash_password


def main() -> None:
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")

    if not email or not password:
        raise SystemExit("Set ADMIN_EMAIL and ADMIN_PASSWORD env vars before running.")

    db = SessionLocal()
    try:
        normalized_email = email.strip().lower()
        force_reset = os.getenv("FORCE_RESET_ADMIN", "").strip() == "1"

        existing = db.query(AdminUser).filter(AdminUser.email == normalized_email).first()
        if existing:
            if force_reset:
                existing.password_hash = hash_password(password)
                existing.is_active = True
                db.commit()
                print(f"Reset admin password: {normalized_email}")
            else:
                print(f"Admin already exists: {normalized_email}")
            return

        user = AdminUser(
            email=normalized_email,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created admin: {normalized_email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()