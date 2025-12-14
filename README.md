# LinkGuard# LinkGuard

LinkGuard is a lightweight phishing and malicious link analysis service designed to be simple, fast, and API-first. The goal is to provide organizations with an easy way to evaluate URLs and record scan activity without requiring deep cybersecurity expertise.

This repository contains the **backend API** for LinkGuard, built with FastAPI and SQLite for local development.

---

## 🚀 Features (Current MVP)

- API key–based authentication (per organization)
- URL analysis endpoint (`POST /api/analyze-url`)
- Scan event logging per organization
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
│   ├── services/     # Business logic (future)
│   ├── db.py         # Database configuration
│   └── main.py       # FastAPI app entrypoint
├── linkguard.db      # Local SQLite DB (gitignored)
└── requirements.txt

---

## 🔐 Authentication

All protected endpoints require an API key passed via the request header:

X-API-Key: <your_api_key>

API keys are associated with an organization and validated on every request.

---

## 🧪 Running Locally

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```
### 2. Install dependencies

pip install -r requirements.txt

### 3. Create environment file

cp .env.exampe .env

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
  "event_id": 1,
  "url": "https://example.com",
  "domain": "example.com",
  "org_id": 1,
  "verdict": "unknown",
  "risk_category": "SUSPICIOUS",
  "reasons": []
}

🛣️ Roadmap
	•	Risk scoring engine
	•	Domain reputation enrichment
	•	Admin endpoints for API key management
	•	Browser extension integration
	•	Hosted SaaS deployment

---

License 
MIT (planned)

