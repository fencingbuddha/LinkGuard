# LinkGuard

LinkGuard is a lightweight phishing and malicious link analysis service designed to be simple, fast, and API-first. The goal is to provide organizations with an easy way to evaluate URLs and record scan activity without requiring deep cybersecurity expertise.

This repository contains the **backend API** for LinkGuard, built with FastAPI and SQLite for local development.

---

## ⚡ Quick Demo (Local)

Spin up a fully working demo (org + admin + API key + seeded data) in under a minute.

```bash
cd backend
python app/init_db.py
python app/scripts/seed_admin.py
python app/scripts/seed_api_key.py
# Optional but recommended for a non-empty dashboard
python app/scripts/seed_scan_events.py
uvicorn app.main:app --reload
```

The console will print:
- Admin login email & password
- API key (use in `X-API-Key` header)
- Backend base URL

> 🔧 Advanced demo tooling and troubleshooting are documented in `backend/scripts/README.md`.

---

## 🚀 Features (Current MVP)

- API key–based authentication (per organization)
- URL analysis endpoint (`POST /api/analyze-url`)
- Deterministic URL risk analysis (IP-based URLs, suspicious TLDs, subdomains, typosquatting)
- Organization-scoped scan context (`org_id`)
- SQLite database for fast local iteration
- Clean project structure designed to scale into a SaaS

---

## 🧱 Tech Stack

- **Python 3.11+** (tested up to 3.14)
- **FastAPI** – API framework
- **SQLAlchemy** – ORM
- **SQLite** – Local development database
- **Uvicorn** – ASGI server

---

## 📁 Project Structure

backend/
├── app/
│   ├── api/          # API routes & dependencies
│   ├── models/       # SQLAlchemy ORM models
│   ├── services/     # Business logic (URL analysis)
│   ├── db.py         # Database configuration
│   └── main.py       # FastAPI app entrypoint
├── tests/            # Unit + API tests (pytest)
├── scripts/          # Dev utilities (API key seeding)
├── pytest.ini        # Pytest configuration
├── linkguard.db      # Local SQLite DB (gitignored)
└── requirements.txt

---

## 🔐 Authentication

All protected endpoints require an API key passed via the request header:

X-API-Key: <your_api_key>

API keys are associated with an organization and validated on every request.

### Creating a Dev API Key

For local development, an API key can be created using the provided seed script:

```bash
cd backend
python -m scripts.seed_api_key
```

This creates an active API key in the local SQLite database. Use the generated key in the `X-API-Key` request header when calling protected endpoints.

---

## 🧪 Running Locally

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```
### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create environment file

cp .env.example .env

### 4. Start the server

cd backend
uvicorn app.main:app --reload
The API key will be available at:
http://127.0.0.1:8000

### Example Request
curl -X POST http://127.0.0.1:8000/api/analyze-url \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"url": "https://example.com"}'

### EXAMPLE Response
{
  "org_id": 1,
  "risk_category": "SAFE",
  "score": 0,
  "explanations": [
    "No suspicious patterns detected"
  ],
  "normalized_url": "https://example.com",
  "host": "example.com"
}

🛣️ Roadmap
	•	Enhanced risk scoring & reputation enrichment
	•	Domain reputation enrichment
	•	Admin endpoints for API key management
	•	Browser extension integration
	•	Hosted SaaS deployment

---

License 
MIT (planned)

## 🐳 Running with Docker (Recommended)

LinkGuard can be run locally using Docker Compose, which is the recommended setup for development.

### Prerequisites
- Docker Desktop (Mac/Windows/Linux)

### Start the backend
From the repository root:

```bash
docker compose up --build
```

The API will be available at:
http://127.0.0.1:8000

### Health check
```bash
curl http://127.0.0.1:8000/health
```

### Notes
- The SQLite database is persisted using a Docker volume.
- Configuration is provided via environment variables (e.g. DATABASE_URL).
- Hot reload is enabled for local development.