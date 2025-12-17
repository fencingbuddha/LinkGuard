from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.api_key import ApiKey
from app.api.deps import _hash_api_key


TEST_API_KEY = "dev-key-123"
TEST_ORG_ID = 1


def _ensure_test_api_key() -> None:
    """Ensure an ACTIVE API key exists for API auth tests.

    CI runners start with an empty SQLite DB, so tests must seed what they need.

    The app stores only a SHA-256 hash of the raw key (plus a short prefix).
    """
    db = SessionLocal()
    try:
        key_hash = _hash_api_key(TEST_API_KEY)
        key_prefix = TEST_API_KEY[:8]

        existing = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if existing:
            existing.is_active = True
            # Ensure revoked keys become usable for this test
            if hasattr(existing, "revoked_at"):
                existing.revoked_at = None
            # Keep org_id stable for assertions / debugging
            existing.org_id = existing.org_id or TEST_ORG_ID
            if hasattr(existing, "key_prefix"):
                existing.key_prefix = key_prefix
        else:
            db.add(
                ApiKey(
                    org_id=TEST_ORG_ID,
                    key_hash=key_hash,
                    key_prefix=key_prefix,
                    is_active=True,
                )
            )

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


def test_analyze_url_ignores_client_supplied_org_id():
    """Client must not be able to override tenant context.

    Even if a request includes an `org_id`, the backend should derive org_id
    from the API key (OrgContext), not from user input.
    """
    _ensure_test_api_key()

    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": TEST_API_KEY},
        json={"url": "https://example.com", "org_id": TEST_ORG_ID + 999},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["org_id"] == TEST_ORG_ID