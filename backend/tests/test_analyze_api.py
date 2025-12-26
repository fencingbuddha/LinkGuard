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
            if hasattr(existing, "revoked_at"):
                existing.revoked_at = None
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

    # Stable demo-friendly contract
    assert "request_id" in body and isinstance(body["request_id"], str)
    assert body["category"] in {"SAFE", "SUSPICIOUS", "DANGEROUS"}
    assert isinstance(body["score"], int)
    assert isinstance(body["explanation"], str) and body["explanation"]

    # Compatibility fields
    assert body["category"] == body["risk_category"]
    assert isinstance(body["explanations"], list)
    assert isinstance(body["normalized_url"], str)


def test_analyze_url_missing_url_returns_400():
    _ensure_test_api_key()

    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": TEST_API_KEY},
        json={"url": ""},
    )
    assert r.status_code == 400
    assert "detail" in r.json()


def test_analyze_url_dev_hook_forces_suspicious():
    _ensure_test_api_key()

    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": TEST_API_KEY},
        json={"url": "https://example.com/?linkguard_test=suspicious"},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["org_id"] == TEST_ORG_ID
    assert body["category"] == "SUSPICIOUS"
    assert body["risk_category"] == "SUSPICIOUS"


def test_analyze_url_ignores_client_supplied_org_id():
    _ensure_test_api_key()

    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": TEST_API_KEY},
        json={"url": "https://example.com", "org_id": 999},
    )
    assert r.status_code == 200
    assert r.json()["org_id"] == TEST_ORG_ID


# ---------------------------
# Rate limiting tests
# ---------------------------

from app.api import deps as deps_mod


def _set_rate_limit(max_requests: int, window_s: int):
    deps_mod.RATE_LIMIT_MAX = max_requests
    deps_mod.RATE_LIMIT_WINDOW_S = window_s


def _clear_rate_buckets():
    deps_mod._RATE_BUCKETS.clear()


def test_analyze_url_rate_limited_returns_429_and_retry_after():
    _ensure_test_api_key()
    _clear_rate_buckets()
    _set_rate_limit(max_requests=2, window_s=60)

    h = {"X-API-Key": TEST_API_KEY}

    r1 = client.post("/api/analyze-url", headers=h, json={"url": "https://example.com"})
    r2 = client.post("/api/analyze-url", headers=h, json={"url": "https://example.com"})
    r3 = client.post("/api/analyze-url", headers=h, json={"url": "https://example.com"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert "retry-after" in {k.lower(): v for k, v in r3.headers.items()}


def test_analyze_url_rate_limit_resets_after_window(monkeypatch):
    _ensure_test_api_key()
    _clear_rate_buckets()
    _set_rate_limit(max_requests=1, window_s=10)

    t = {"now": 1000.0}

    def fake_time():
        return t["now"]

    monkeypatch.setattr(deps_mod.time, "time", fake_time)

    h = {"X-API-Key": TEST_API_KEY}

    r1 = client.post("/api/analyze-url", headers=h, json={"url": "https://example.com"})
    assert r1.status_code == 200

    r2 = client.post("/api/analyze-url", headers=h, json={"url": "https://example.com"})
    assert r2.status_code == 429

    t["now"] += 11.0
    r3 = client.post("/api/analyze-url", headers=h, json={"url": "https://example.com"})
    assert r3.status_code == 200

def test_analyze_url_service_failure_returns_safe_fallback(monkeypatch):
    _ensure_test_api_key()

    # Patch the service layer the endpoint calls so it throws
    from app.api import analyze as analyze_mod

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(analyze_mod, "analyze_url_service", boom)

    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": TEST_API_KEY},
        json={"url": "https://example.com"},
    )

    assert r.status_code == 200
    body = r.json()

    # Still a stable contract even on failure
    assert body["org_id"] == TEST_ORG_ID
    assert body["category"] in {"SAFE", "SUSPICIOUS", "DANGEROUS"}
    assert isinstance(body["score"], int)
    assert isinstance(body["explanation"], str) and body["explanation"]
    assert "request_id" in body and isinstance(body["request_id"], str) and body["request_id"]