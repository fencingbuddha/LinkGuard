

"""Seed ScanEvent rows for local/dev dashboards.

Usage examples:
  python scripts/seed_scan_events.py
  python scripts/seed_scan_events.py --count 200 --org-ids 1 2 3
  python scripts/seed_scan_events.py --org-ids 1 --days 30 --delete-existing

Notes:
- This script is intended for local development only.
- It writes to whatever DB your app is configured to use via app.db SessionLocal.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from app.db import SessionLocal
from app.models.scan_event import RiskCategory, ScanEvent


DEFAULT_DOMAINS: Sequence[str] = (
    "example.com",
    "google.com",
    "github.com",
    "login-verify-account.net",
    "secure-reset-password.com",
    "update-billing-info.org",
    "microsoft-support-login.com",
    "paypal-alerts-secure.net",
)


def _now_utc() -> datetime:
    # timezone-aware UTC timestamp (avoids utcnow() deprecation warnings)
    return datetime.now(timezone.utc)


def _pick_risk_category(rng: random.Random) -> RiskCategory:
    # Mostly SAFE, some SUSPICIOUS, few DANGEROUS
    risks = (RiskCategory.SAFE, RiskCategory.SUSPICIOUS, RiskCategory.DANGEROUS)
    weights = (0.70, 0.20, 0.10)
    return rng.choices(risks, weights=weights, k=1)[0]


def seed_scan_events(
    *,
    org_ids: Sequence[int],
    count: int,
    days: int,
    domains: Sequence[str],
    delete_existing: bool,
    rng_seed: int | None,
) -> int:
    rng = random.Random(rng_seed)
    s = SessionLocal()

    try:
        if delete_existing:
            deleted = (
                s.query(ScanEvent)
                .filter(ScanEvent.org_id.in_(list(org_ids)))
                .delete(synchronize_session=False)
            )
            # Not committing yet; we'll commit once at the end.
            print(f"Deleted {deleted} existing scan_events for org_ids={list(org_ids)}")

        now = _now_utc()

        for _ in range(count):
            org_id = rng.choice(list(org_ids))
            domain = rng.choice(list(domains))
            risk = _pick_risk_category(rng)

            # Random timestamp in the last `days` days
            ts = now - timedelta(
                days=rng.randint(0, max(days - 1, 0)),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            s.add(
                ScanEvent(
                    org_id=org_id,
                    domain=domain,
                    risk_category=risk,
                    timestamp=ts,
                )
            )

        s.commit()

        total = s.query(ScanEvent).count()
        print(f"Seeded {count} scan_events. Total rows now: {total}")
        return count

    finally:
        s.close()


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed ScanEvent rows for local/dev dashboards")
    p.add_argument(
        "--org-ids",
        nargs="+",
        type=int,
        default=[1, 2, 3],
        help="Organization IDs to seed (default: 1 2 3)",
    )
    p.add_argument(
        "--count",
        type=int,
        default=75,
        help="How many scan_events to create (default: 75)",
    )
    p.add_argument(
        "--days",
        type=int,
        default=14,
        help="Spread timestamps across the last N days (default: 14)",
    )
    p.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete existing scan_events for the provided org_ids before seeding",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible data (default: none)",
    )
    return p.parse_args(list(argv) if argv is not None else None)


def main() -> None:
    args = _parse_args()

    if not args.org_ids:
        raise SystemExit("At least one org_id is required")

    if args.count <= 0:
        raise SystemExit("--count must be > 0")

    if args.days <= 0:
        raise SystemExit("--days must be > 0")

    seed_scan_events(
        org_ids=args.org_ids,
        count=args.count,
        days=args.days,
        domains=DEFAULT_DOMAINS,
        delete_existing=bool(args.delete_existing),
        rng_seed=args.seed,
    )


if __name__ == "__main__":
    main()