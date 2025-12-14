from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.api_key import ApiKey, ApiKeyStatus


TEST_API_KEY = "dev-key-123"
TEST_ORG_ID = 1


def _ensure_test_api_key() -> None:
    """Ensure an ACTIVE API key exists for API auth tests.

    CI runners start with an empty SQLite DB, so tests must seed what they need.
    """
    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key == TEST_API_KEY).first()
        if existing:
            existing.status = ApiKeyStatus.ACTIVE
            # Keep org_id stable for assertions / debugging
            existing.org_id = existing.org_id or TEST_ORG_ID
        else:
            db.add(ApiKey(key=TEST_API_KEY, org_id=TEST_ORG_ID, status=ApiKeyStatus.ACTIVE))
        db.commit()
    finally:
        db.close()


client = TestClient(app)


def test_analyze_url_missing_api_key():
    r = client.post("/api/analyze-url", json={"url": "https://example.com"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing API key"


def test_analyze_url_invalid_api_key():
    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": "nope"},
        json={"url": "https://example.com"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid API key"


def test_analyze_url_valid_api_key():
    _ensure_test_api_key()

    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": TEST_API_KEY},
        json={"url": "https://example.com"},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["org_id"] == TEST_ORG_ID
    assert "risk_category" in body
    assert "score" in body
    assert "explanations" in body