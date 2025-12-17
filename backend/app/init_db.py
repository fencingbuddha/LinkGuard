from app.db import Base, engine


def init_db() -> None:
    """Create all tables in the database."""
    # IMPORTANT: import models so they register with Base.metadata
    # (Avoid relying on side-effect imports elsewhere.)
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()