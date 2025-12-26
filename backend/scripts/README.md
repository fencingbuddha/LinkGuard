# Scan Event Seeding for Admin Dashboard (Dev Only)

> ℹ️ For full project setup and quick demo instructions, see the root `README.md`.

This folder contains **development-only scripts** used to populate the database with realistic sample data so the **Admin Dashboard** displays meaningful metrics (totals, risk distribution, top risky domains, and daily trends).

> ⚠️ **DO NOT RUN IN PRODUCTION**
> These scripts insert synthetic data directly into the database and are intended **only** for local development and demos.

---

## What This Is

- A helper script to seed the `scan_events` table with realistic-looking data
- Enables `/api/admin/stats` to return non-zero results
- Makes the dashboard usable immediately without waiting for real traffic

Primary script:
- `seed_scan_events.py`

---

## When To Use This

Use this script when:
- The admin dashboard shows all zeros
- You’ve just set up a fresh local database
- You want demo-ready analytics for screenshots or walkthroughs
- You’re validating Issue #50 (Admin stats population)

---

## Prerequisites

- Backend running locally
- Database initialized with organizations (IDs typically `1`, `2`, `3`)
- Python virtual environment activated

```bash
cd backend
source .venv/bin/activate
```

---

## Basic Usage

Seed the default dataset (75 events across orgs 1–3 over the last 14 days):

```bash
python scripts/seed_scan_events.py
```

---

## Common Options

Seed 200 events across orgs 1, 2, and 3:

```bash
python scripts/seed_scan_events.py --count 200 --org-ids 1 2 3
```

Seed only org 1 and delete existing data first:

```bash
python scripts/seed_scan_events.py --org-ids 1 --delete-existing --count 100
```

Spread data across the last 30 days:

```bash
python scripts/seed_scan_events.py --days 30
```

Use a fixed random seed for reproducible data:

```bash
python scripts/seed_scan_events.py --seed 42
```

---

## What Data Gets Created

Each seeded `ScanEvent` includes:

- `org_id`: one of the provided organization IDs
- `domain`: sampled from a predefined list of common and risky domains
- `risk_category`: weighted distribution
  - ~70% SAFE
  - ~20% SUSPICIOUS
  - ~10% DANGEROUS
- `timestamp`: randomly distributed across the last N days

This produces realistic admin metrics without manual setup.

---

## Verifying It Worked

### 1) Check database row count

```bash
python -c "from app.db import SessionLocal; from app.models.scan_event import ScanEvent; s=SessionLocal(); print('scan_events:', s.query(ScanEvent).count()); s.close()"
```

### 2) Check the stats API

```bash
curl -s "http://127.0.0.1:8000/api/admin/stats?org_id=1" | jq
```

### 3) Check the dashboard

Ensure the dashboard is configured with a valid org ID:

`dashboard/.env.local`
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ORG_ID=1
```

Restart the dashboard:

```bash
npm run dev
```

You should now see non-zero values on the Admin Dashboard.

---

## Common Gotchas

- **Dashboard still shows zeros** → Wrong `VITE_ORG_ID` or Vite not restarted
- **404 from `/api/admin/stats`** → Organization ID does not exist
- **Data disappears** → Local DB was reset or migrations re-run

---

## Related Issues

- Issue #50 — Populate real scan metrics for admin dashboard

---

Happy hacking 👋