import pytest
from fastapi.testclient import TestClient

from app.api.deps import rate_limit_analyze_url
from app.main import app


def _headers(api_key: str = "dev-key-123") -> dict:
    return {"X-API-Key": api_key}


client = TestClient(app)


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    # /api/analyze-email shares the same rate limiter dependency as /api/analyze-url.
    # Disable it in unit tests to avoid cross-test interference.
    app.dependency_overrides[rate_limit_analyze_url] = lambda: None
    try:
        yield
    finally:
        app.dependency_overrides.pop(rate_limit_analyze_url, None)


def test_analyze_email_sender_wins_over_safe_links():
    """overall_score = max(sender_score, highest_link_score) where sender wins."""
    payload = {
        "links": ["https://google.com"],
        "from_name": "IT Support",
        "from_email": "it-support@gmail.com",
        "reply_to_emails": ["helpdesk@company.com"],
        "source": "outlook_web",
    }

    r = client.post("/api/analyze-email", json=payload, headers=_headers())
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["sender"]["risk_category"] == "SUSPICIOUS"
    assert 25 <= int(data["sender"]["score"]) < 60

    assert data["category"] == "SUSPICIOUS"
    assert data["risk_category"] == "SUSPICIOUS"
    assert 25 <= int(data["score"]) < 60

    # Unified verdict: overall score should match sender score and be >= the highest link score
    link_scores = [int(l["score"]) for l in data.get("links", [])]
    assert int(data["score"]) == int(data["sender"]["score"])
    assert int(data["score"]) >= (max(link_scores) if link_scores else 0)

    # Sender signals should be present for this case
    assert "reply_to_mismatch" in data["sender"].get("signals", [])
    assert "free_mail_provider" in data["sender"].get("signals", [])


def test_analyze_email_link_wins_over_safe_sender():
    """overall_score = max(sender_score, highest_link_score) where link wins."""
    payload = {
        "links": ["https://example.com/?linkguard_test=danger"],
        "from_name": "Alice",
        "from_email": "alice@company.com",
        "source": "outlook_web",
    }

    r = client.post("/api/analyze-email", json=payload, headers=_headers())
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["sender"]["score"] == 0
    assert data["sender"]["risk_category"] == "SAFE"

    assert data["score"] == 100
    assert data["category"] == "DANGEROUS"
    assert data["risk_category"] == "DANGEROUS"

    link_scores = [int(l["score"]) for l in data.get("links", [])]
    assert int(data["score"]) == max(link_scores)
    assert int(data["score"]) >= int(data["sender"]["score"])

    assert any("1 dangerous link(s)" in e for e in data["explanations"])


def test_analyze_email_links_only_payload_still_works():
    """Backwards compatible: caller can send only links and still get sender block."""
    payload = {
        "links": ["https://example.com/?linkguard_test=suspicious"],
        "source": "outlook_web",
    }

    r = client.post("/api/analyze-email", json=payload, headers=_headers())
    assert r.status_code == 200, r.text
    data = r.json()

    assert "sender" in data
    assert data["sender"]["risk_category"] == "SAFE"
    assert data["sender"]["score"] == 0

    assert data["category"] == "SUSPICIOUS"
    assert data["risk_category"] == "SUSPICIOUS"
    assert 25 <= int(data["score"]) < 60

    # Unified verdict: with no sender signals, overall should equal the link score
    assert len(data["links"]) == 1
    assert int(data["score"]) == int(data["links"][0]["score"])
    assert data["links"][0]["risk_category"] == "SUSPICIOUS"


def test_analyze_email_requires_links_validation_error():
    # links is required by the Pydantic model, so FastAPI returns 422
    r = client.post("/api/analyze-email", json={"source": "outlook_web"}, headers=_headers())
    assert r.status_code == 422