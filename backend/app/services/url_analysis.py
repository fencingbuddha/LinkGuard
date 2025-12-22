# app/services/url_analysis.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse
import ipaddress
import re

SUSPICIOUS_TLDS = {
    "zip", "mov", "top", "xyz", "click", "country", "stream", "gq", "tk"
}


BRANDS = {"google", "paypal", "microsoft", "apple", "amazon"}

# Common phishing-related path keywords (MVP heuristic)
SUSPICIOUS_PATH_KEYWORDS = {
    "login", "signin", "sign-in", "verify", "verification",
    "password", "reset", "update", "secure", "account",
    "billing", "bank", "wallet", "confirm"
}

class RiskCategory(str, Enum):
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    DANGEROUS = "DANGEROUS"

def _ensure_scheme(raw: str) -> str:
    raw = raw.strip()
    if "://" not in raw:
        return "https://" + raw
    return raw

def _is_ip_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except Exception:
        return False

# Simple, deterministic host validation for MVP.
# We treat non-domain-like hosts (spaces, illegal chars, no dot and not an IP) as invalid.
_HOST_RE = re.compile(r"^[a-z0-9.-]+$")


def _is_plausible_host(host: str) -> bool:
    if not host:
        return False
    if " " in host:
        return False
    if not _HOST_RE.match(host):
        return False
    # Require either a dot-domain or a literal IP
    if "." not in host:
        return _is_ip_host(host)
    return True

def _get_tld(host: str) -> str | None:
    parts = host.split(".")
    if len(parts) < 2:
        return None
    return parts[-1]

def _subdomain_count(host: str) -> int:
    # crude: counts labels minus last 2 (eTLD+1 approximation)
    parts = host.split(".")
    if len(parts) <= 2:
        return 0
    return len(parts) - 2

def _looks_like_typosquat(host: str) -> tuple[bool, str | None]:
    # super simple: compare second-level label to brand list with basic substitutions
    parts = host.split(".")
    if len(parts) < 2:
        return (False, None)
    sld = parts[-2]

    normalized = (
        sld.replace("0", "o")
           .replace("1", "l")
           .replace("3", "e")
    )

    if normalized in BRANDS and sld != normalized:
        return (True, f"Possible typosquatting of brand '{normalized}'")

    return (False, None)

def analyze_url(url: str) -> dict:
    explanations: list[str] = []
    score = 0

    try:
        normalized_url = _ensure_scheme(url)
        parsed = urlparse(normalized_url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()

        if not host:
            return {
                "risk_category": RiskCategory.SUSPICIOUS.value,
                "score": 40,
                "explanations": ["Invalid URL (missing host)"],
                "normalized_url": normalized_url,
                "host": None,
            }

        if not _is_plausible_host(host):
            return {
                "risk_category": RiskCategory.SUSPICIOUS.value,
                "score": 40,
                "explanations": ["Invalid or unparseable URL"],
                "normalized_url": normalized_url,
                "host": None,
            }

        # Rule: IP-based URL
        if _is_ip_host(host):
            score += 70
            explanations.append("Host is an IP address (common in phishing)")

        # Rule: Suspicious TLD
        tld = _get_tld(host)
        if tld and tld in SUSPICIOUS_TLDS:
            score += 25
            explanations.append(f"Suspicious TLD: .{tld}")

        # Rule: Multiple subdomains
        sub_count = _subdomain_count(host)
        if sub_count >= 4:
            score += 25
            explanations.append(f"Many subdomains ({sub_count})")

        # Rule: Simple typosquatting
        is_typo, msg = _looks_like_typosquat(host)
        if is_typo and msg:
            score += 30
            explanations.append(msg)

        # Rule: Suspicious path keywords (e.g., login / verify pages)
        if path:
            for kw in SUSPICIOUS_PATH_KEYWORDS:
                if kw in path:
                    score += 30
                    explanations.append(f"Suspicious path keyword: '{kw}'")
                    break

        # Category mapping
        if score >= 60:
            cat = RiskCategory.DANGEROUS
        elif score >= 25:
            cat = RiskCategory.SUSPICIOUS
        else:
            cat = RiskCategory.SAFE

        return {
            "risk_category": cat.value,
            "score": min(score, 100),
            "explanations": explanations or ["No suspicious patterns detected"],
            "normalized_url": normalized_url,
            "host": host,
        }

    except Exception:
        normalized = url
        try:
            normalized = _ensure_scheme(url)
        except Exception:
            pass

        return {
            "risk_category": RiskCategory.SUSPICIOUS.value,
            "score": 40,
            "explanations": ["Invalid or unparseable URL"],
            "normalized_url": normalized,
            "host": None,
        }