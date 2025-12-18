# Performance Notes — /api/analyze-url

Issue: #21  
Date: 2025-12-18  
Environment:
- Machine: Cameron’s MacBook Pro
- Backend: uvicorn (reload: on)
- DB: SQLite (local)
- Notes: local dev, single process, no cache

## Test Setup
Endpoint: POST /api/analyze-url  
Base URL: http://127.0.0.1:8000  
Requests: 100  
Concurrency: 1 (sequential)  
Payload: {"url":"https://example.com"}

## Results
- Avg latency: 2.46ms
- p95 latency: 2.78ms
- Max latency: 31.75ms
- Errors: 0/100

## ScanEvent Persistence Check
Expected: 1 ScanEvent per request (org_id, domain, risk_category, timestamp)

Before count: 75
After count: 175
Delta: +100

## Observations / Follow-ups
- Local development test with sequential requests and API key authentication enabled.
- Endpoint comfortably meets MVP performance target (<500ms average).
- ScanEvent rows are persisted correctly for each analyze request, enabling accurate admin dashboard analytics.
