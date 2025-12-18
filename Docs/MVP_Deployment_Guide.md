# LinkGuard MVP Deployment Guide (Local Dev)

This guide brings up the LinkGuard MVP end-to-end on a clean machine:
- Backend API (FastAPI)
- Admin Dashboard (Vite)
- Chrome Extension (MV3)

> MVP note: rate limiting and API key auth are enabled; persistence is best-effort.

This document is written to be copy/paste friendly. All commands assume a Unix-like shell (macOS/Linux). Windows users should use WSL.

---

## Prereqs
- Python 3.12+ (project currently using 3.14 locally)
- Node 18+ (or 20+)
- Git
- (Optional) Docker + docker compose

Repo layout:
- `backend/` = FastAPI app
- `dashboard/` = Vite admin UI
- `extension/` = Chrome MV3 extension (path may differ)

---

## 1) Clone + create virtualenv

```bash
git clone <your-repo-url>
cd LinkGuard

python -m venv .venv
source .venv/bin/activate
```

## 2) Backend setup (FastAPI)

From repo root:

```bash
cd backend
pip install -r requirements.txt
```

### 2.1 Configure local environment

⚠️ These values are **development-only** and are intentionally insecure. Do not reuse them in production.

These are **dev-only** values.

```bash
# Required for API key hashing
export API_KEY_PEPPER="dev-pepper-change-me"

# Admin auth (for /api/admin/*)
export JWT_SECRET="dev-jwt-secret-change-me"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD='Admin123!ChangeMe'
export FORCE_RESET_ADMIN=1

# Rate limiting (default values shown)
export RATE_LIMIT_MAX=5
export RATE_LIMIT_WINDOW_S=60

# CORS allowlist (dashboard dev server)
export CORS_ORIGINS="http://localhost:5173"
```

Seed the admin user:

```bash
python -m app.scripts.seed_admin
```

### 2.2 Seed a dev API key (local only)

This API key is used by curl tests, the admin dashboard, and the Chrome extension during local development.

```bash
export DEV_ORG_ID=1
export DEV_API_KEY="dev-key-123-LOCAL-ONLY"

python -m app.scripts.seed_api_key
```

### 2.3 Run the backend

```bash
uvicorn app.main:app --reload
```

---

## 3) Verify security hardening (copy/paste)

Run the following commands from a **second terminal** while the backend server is running.

Run these commands from **another terminal** while uvicorn is running.

### 3.1 Valid API key → 200

```bash
curl -i -X POST "http://127.0.0.1:8000/api/analyze-url" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DEV_API_KEY" \
  -d '{"url":"https://example.com"}'
```

Expected: `HTTP/1.1 200 OK`

### 3.2 Missing API key → 401

```bash
curl -i -X POST "http://127.0.0.1:8000/api/analyze-url" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}' | sed -n '1,12p'
```

Expected: `HTTP/1.1 401 Unauthorized` and body `{"detail":"Missing API key"}`

### 3.3 Rate limiting → 429 after `RATE_LIMIT_MAX`

```bash
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $DEV_API_KEY" \
    -d '{"url":"https://example.com"}' \
    http://127.0.0.1:8000/api/analyze-url
done
```

Expected (with `RATE_LIMIT_MAX=5`): first five `200`, then `429`.

To inspect `Retry-After`:

```bash
curl -i -X POST "http://127.0.0.1:8000/api/analyze-url" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DEV_API_KEY" \
  -d '{"url":"https://example.com"}' | sed -n '1,25p'
```

Expected: `HTTP/1.1 429 Too Many Requests` and a `retry-after: <seconds>` header.

### 3.4 CORS allowlist checks

Allowed headers (should pass):

```bash
curl -i -X OPTIONS "http://127.0.0.1:8000/api/analyze-url" \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-api-key" | sed -n '1,25p'
```

Expected: `HTTP/1.1 200 OK` and `access-control-allow-origin: http://localhost:5173`

Disallowed headers (should fail):

```bash
curl -i -X OPTIONS "http://127.0.0.1:8000/api/analyze-url" \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: x-not-allowed" | sed -n '1,25p'
```

Expected: `HTTP/1.1 400 Bad Request` with `Disallowed CORS headers`

---

## 4) Dashboard setup (Vite)

From repo root:

```bash
cd dashboard
npm install
```

Create `dashboard/.env.local`:

```bash
cat > .env.local <<'EOF'
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ORG_ID=1
EOF
```

Run the dashboard:

```bash
npm run dev
```

Open: `http://localhost:5173`

---

## 5) Chrome extension (MV3)

The Chrome extension is not yet finalized. Once the extension directory is stabilized, this section will include build and load instructions for Chrome (MV3).

---

## Known MVP Limitations

- In-memory rate limiting resets on server restart
- API keys are manually seeded for development
- No HTTPS or production hardening is applied
- No background workers or async persistence guarantees

These limitations are intentional for the MVP and tracked in future issues.
