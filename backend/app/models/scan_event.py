from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RiskCategory(str, enum.Enum):
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    DANGEROUS = "DANGEROUS"


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Optional context for email-based scans (Outlook add-in, etc.)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    scan_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    # Optional original artifact identifier (e.g., full URL or mailto:address) for debugging
    artifact: Mapped[str | None] = mapped_column(Text, nullable=True)

    risk_category: Mapped[RiskCategory] = mapped_column(
        Enum(RiskCategory), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    organization: Mapped["Organization"] = relationship(back_populates="scan_events")


if TYPE_CHECKING:
    from app.models.organization import Organization