from app.db import Base, engine
from app.models import Organization, ApiKey, ScanEvent  # noqa: F401


def init_db() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()