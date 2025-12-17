from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Store ONLY a hash of the API key (never the plaintext key).
    # If you use sha256 hex, this is 64 chars.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # Optional convenience field for admin display/debugging (not sensitive).
    # Example: first 8 chars of the raw key.
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # Soft revoke
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="api_keys")


if TYPE_CHECKING:
    from app.models.organization import Organization