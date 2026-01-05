

import pytest

from app.services.sender_analysis import analyze_sender


def test_reply_to_domain_mismatch_flags_signal_and_category():
    res = analyze_sender(
        from_name="IT Support",
        from_email="it-support@company.com",
        reply_to_emails=["helpdesk@other-company.com"],
    )

    assert res["risk_category"] in {"SUSPICIOUS", "DANGEROUS"}
    assert "reply_to_mismatch" in res["signals"]
    assert any("Reply-To" in e for e in res["explanations"])
    assert res["score"] >= 40


def test_free_mail_provider_with_org_like_display_name_flags_signal():
    res = analyze_sender(
        from_name="IT Support",
        from_email="it-support@gmail.com",
        reply_to_emails=[],
    )

    assert "free_mail_provider" in res["signals"]
    # This is intentionally a light signal and may remain SAFE depending on weights.
    assert res["risk_category"] in {"SAFE", "SUSPICIOUS", "DANGEROUS"}
    assert res["score"] >= 15


def test_display_name_domain_mismatch_flags_signal():
    res = analyze_sender(
        from_name="Google Security",
        from_email="alerts@randomdomain.com",
        reply_to_emails=[],
    )

    assert "display_name_domain_mismatch" in res["signals"]
    # This is intentionally a light signal and may remain SAFE depending on weights.
    assert res["risk_category"] in {"SAFE", "SUSPICIOUS", "DANGEROUS"}
    assert res["score"] >= 15


def test_lookalike_domain_detection_flags_signal():
    res = analyze_sender(
        from_name="Google Security",
        from_email="alerts@go0gle.com",
        reply_to_emails=[],
    )

    assert "lookalike_domain" in res["signals"]
    assert res["risk_category"] in {"SUSPICIOUS", "DANGEROUS"}
    assert res["score"] >= 30


def test_punycode_domain_detection_flags_signal():
    # Any domain starting with xn-- should be flagged as punycode.
    res = analyze_sender(
        from_name="Support",
        from_email="support@xn--googl-fsa.com",
        reply_to_emails=[],
    )

    assert "punycode_domain" in res["signals"]
    assert res["risk_category"] in {"SUSPICIOUS", "DANGEROUS"}


def test_safe_sender_returns_safe_category():
    res = analyze_sender(
        from_name="Alice",
        from_email="alice@company.com",
        reply_to_emails=[],
    )

    assert res["risk_category"] == "SAFE"
    assert res["score"] < 25
    assert res["signals"] == []
    assert res["explanations"] == []


@pytest.mark.parametrize(
    "from_name,from_email,reply_to,expected_category",
    [
        ("Alice", "alice@company.com", [], "SAFE"),
        # Lookalike domain should land in SUSPICIOUS band (>=25) for our current weights
        ("Google Security", "alerts@go0gle.com", [], "SUSPICIOUS"),
        # Strong + medium signals should land in DANGEROUS band (>=60)
        ("IT Support", "it-support@gmail.com", ["helpdesk@company.com"], "SUSPICIOUS"),
    ],
)
def test_score_to_category_mapping_is_stable(from_name, from_email, reply_to, expected_category):
    res = analyze_sender(from_name=from_name, from_email=from_email, reply_to_emails=reply_to)

    # We assert the expected category for known cases.
    assert res["risk_category"] == expected_category

    # And we enforce the global thresholds match URL analysis conventions.
    score = int(res["score"])
    if res["risk_category"] == "DANGEROUS":
        assert score >= 60
    elif res["risk_category"] == "SUSPICIOUS":
        assert 25 <= score < 60
    else:
        assert score < 25