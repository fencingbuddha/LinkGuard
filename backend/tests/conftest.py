import pytest

from app.db import engine, Base
from app.models.api_key import ApiKey  # ensures model is imported/registered
     # <-- adjust if your Base lives elsewhere


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    # Create all tables in the test DB before any tests execute
    Base.metadata.create_all(bind=engine)
    yield