from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

import os
from pathlib import Path

# Make the default SQLite DB location deterministic (relative to the backend folder),
# so running from different working directories doesn't create multiple DB files.
_backend_dir = Path(__file__).resolve().parents[1]  # .../backend/app -> .../backend
_default_sqlite_path = _backend_dir / "linkguard.db"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_sqlite_path}")

# For SQLite in a single-process FastAPI app, this flag is fine.
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

from typing import Generator

from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a DB session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()