from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ApiKeyStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    status: Mapped[ApiKeyStatus] = mapped_column(
        Enum(
            ApiKeyStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=False,
        ),
        default=ApiKeyStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="api_keys")


if TYPE_CHECKING:
    from app.models.organization import Organization