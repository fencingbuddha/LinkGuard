from fastapi.testclient import TestClient
from app.main import app

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
    r = client.post(
        "/api/analyze-url",
        headers={"X-API-Key": "dev-key-123"},
        json={"url": "https://example.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "org_id" in body
    assert "risk_category" in body
    assert "score" in body
    assert "explanations" in body