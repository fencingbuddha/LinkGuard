"""Lightweight sender risk analysis.

MVP goals:
- No external dependencies (no DNS/SPF/DKIM/DMARC lookups).
- Explainable, deterministic heuristics.
- Score/category mapping matches URL analysis thresholds.

Public API:
    analyze_sender(from_name, from_email, reply_to_emails) -> {
        "score": int,
        "risk_category": "SAFE"|"SUSPICIOUS"|"DANGEROUS",
        "explanations": list[str],
        "signals": list[str],
    }
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, List, Dict


# Keep this list small & obvious; expand later with telemetry.
FREE_EMAIL_PROVIDERS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "proton.me",
    "protonmail.com",
    "pm.me",
    "gmx.com",
}


# High-value brand tokens for mismatch/lookalike checks.
# This is intentionally conservative; false positives are worse than misses for v1.
BRAND_TOKENS = {
    "google": {"google.com"},
    "microsoft": {"microsoft.com", "office.com", "live.com"},
    "paypal": {"paypal.com"},
    "apple": {"apple.com", "icloud.com", "me.com"},
    "amazon": {"amazon.com"},
    "docusign": {"docusign.com"},
    "okta": {"okta.com"},
    "dropbox": {"dropbox.com"},
    "linkedin": {"linkedin.com"},
    "facebook": {"facebook.com", "meta.com"},
    "instagram": {"instagram.com"},
}


ORGISH_TOKENS = {
    "support",
    "helpdesk",
    "help",
    "security",
    "admin",
    "it",
    "billing",
    "invoice",
    "accounts",
    "team",
    "service",
    "customer",
    "verification",
    "verify",
    "alert",
    "notice",
}


LEET_MAP = str.maketrans({
    "0": "o",
    "1": "l",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "8": "b",
    "9": "g",
})


def risk_category_from_score(score: int) -> str:
    """Match url_analysis thresholds: >=60 dangerous, >=25 suspicious."""
    if score >= 60:
        return "DANGEROUS"
    if score >= 25:
        return "SUSPICIOUS"
    return "SAFE"


def _extract_domain(email: Optional[str]) -> str:
    if not email:
        return ""
    email = email.strip()
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def _base_domain(domain: str) -> str:
    """Best-effort base domain (no public suffix list; keep it simple).

    Returns last two labels for typical domains: a.b.c -> b.c
    For single-label or empty, returns as-is.
    """
    parts = [p for p in (domain or "").split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain or ""


def _looks_organizational_display_name(name: Optional[str]) -> bool:
    if not name:
        return False
    n = name.strip().lower()
    if not n:
        return False
    if "@" in n:
        return False
    # Heuristic: org-ish if it contains certain tokens or looks like a role/team.
    if any(tok in n for tok in ORGISH_TOKENS):
        return True
    # Two+ words is often a display name; treat it as org-ish only if it includes a role-y word.
    if len(n.split()) >= 2 and re.search(r"\b(it|security|support|billing|accounts)\b", n):
        return True
    return False


def _find_brand_in_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for brand in BRAND_TOKENS.keys():
        if brand in t:
            return brand
    return None


def _is_free_provider(domain: str) -> bool:
    return (domain or "").lower() in FREE_EMAIL_PROVIDERS


def _has_punycode(domain: str) -> bool:
    # IDN punycode label indicator.
    return "xn--" in (domain or "").lower()


def _looks_like_brand_leetspeak(domain: str) -> Optional[str]:
    """Detect obvious digit-substitution lookalikes.

    Example: go0gle.com -> google
    Returns brand token if a match is found.
    """
    d = (domain or "").lower()
    if not d:
        return None

    # Only consider cases where there are digits or punycode; otherwise too many false positives.
    if not re.search(r"\d", d) and not _has_punycode(d):
        return None

    # Compare against each brand's primary label.
    label = d.split(".")[0]
    normalized = label.translate(LEET_MAP)
    for brand in BRAND_TOKENS.keys():
        if normalized == brand and label != brand:
            return brand
    return None


def analyze_sender(
    *,
    from_name: Optional[str],
    from_email: Optional[str],
    reply_to_emails: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    """Analyze sender risk.

    Parameters
    - from_name: display name ("IT Helpdesk")
    - from_email: sender email ("support@corp.com")
    - reply_to_emails: list of Reply-To addresses (if any)
    """
    signals: List[str] = []
    explanations: List[str] = []
    score = 0

    from_domain = _extract_domain(from_email)
    from_base = _base_domain(from_domain)

    reply_to_domains = []
    if reply_to_emails:
        for r in reply_to_emails:
            d = _extract_domain(str(r))
            if d:
                reply_to_domains.append(d)

    # 1) Reply-To domain mismatch (strong signal)
    if from_domain and reply_to_domains:
        # Mismatch if ANY reply-to base domain differs from from base.
        mismatch = any(_base_domain(d) != from_base for d in reply_to_domains)
        if mismatch:
            signals.append("reply_to_mismatch")
            explanations.append("Reply-To domain does not match From domain.")
            score += 40

    # 2) Free-mail provider used for organizational display name (light/medium)
    if from_domain and _is_free_provider(from_domain) and _looks_organizational_display_name(from_name):
        signals.append("free_mail_provider")
        explanations.append("Sender uses a free email provider for an organizational-looking display name.")
        score += 15

    # 3) Display name vs sender domain mismatch (light)
    brand_in_name = _find_brand_in_text(from_name or "")
    if brand_in_name and from_domain:
        allowed_domains = BRAND_TOKENS.get(brand_in_name, set())
        if _base_domain(from_domain) not in {_base_domain(d) for d in allowed_domains}:
            signals.append("display_name_domain_mismatch")
            explanations.append("Display name suggests a brand/organization that doesn't match the sender domain.")
            score += 15

    # 4) Lookalike / homoglyph domain detection (medium)
    # 4a) Punycode is a strong indicator of homograph attempts (still can be legitimate)
    if from_domain and _has_punycode(from_domain):
        signals.append("punycode_domain")
        explanations.append("Sender domain contains punycode (xn--), which is sometimes used for lookalike domains.")
        score += 30

    # 4b) Leetspeak brand lookalikes (go0gle, micr0soft, etc.)
    if from_domain:
        brand_like = _looks_like_brand_leetspeak(from_domain)
        if brand_like:
            signals.append("lookalike_domain")
            explanations.append("Sender domain appears to be a lookalike of a well-known brand.")
            score += 35

    # Cap score to 100 for consistency with URL scoring.
    score = max(0, min(int(score), 100))
    risk_category = risk_category_from_score(score)

    return {
        "score": score,
        "risk_category": risk_category,
        "explanations": explanations,
        "signals": signals,
    }
