# backend/tests/test_url_analysis.py
import pytest

from app.services.url_analysis import analyze_url

def test_safe_basic_domain():
    r = analyze_url("https://example.com")
    assert r["risk_category"] == "SAFE"
    assert r["score"] >= 0
    assert r["explanations"]

def test_missing_scheme_gets_added():
    r = analyze_url("example.com")
    assert r["normalized_url"].startswith("https://")

def test_invalid_url_is_suspicious():
    r = analyze_url("not a url")
    assert r["risk_category"] in ("SUSPICIOUS", "DANGEROUS")
    assert r["explanations"]

def test_ip_based_url_is_dangerous():
    r = analyze_url("http://192.168.0.1/login")
    assert r["risk_category"] == "DANGEROUS"

def test_suspicious_tld_flags():
    r = analyze_url("https://whatever.xyz")
    assert r["risk_category"] in ("SUSPICIOUS", "DANGEROUS")
    assert any("TLD" in e or ".xyz" in e for e in r["explanations"])

def test_many_subdomains_flags():
    r = analyze_url("https://a.b.c.d.e.example.com")
    assert r["risk_category"] in ("SUSPICIOUS", "DANGEROUS")
    assert any("subdomain" in e.lower() for e in r["explanations"])

def test_typosquatting_flags():
    r = analyze_url("https://g00gle.com")
    assert r["risk_category"] in ("SUSPICIOUS", "DANGEROUS")
    assert any("typo" in e.lower() or "brand" in e.lower() for e in r["explanations"])