from datetime import datetime
from typing import List

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    scan_events: Mapped[List["ScanEvent"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

from app.models.api_key import ApiKey  # type: ignore  # circular import safe at runtime
from app.models.scan_event import ScanEvent  # type: ignore
