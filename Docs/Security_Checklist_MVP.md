# LinkGuard MVP Security Checklist

This document captures baseline security hygiene implemented for the LinkGuard MVP.
Scope is intentionally limited to local development and early production readiness.

---

## Secrets / Configuration
- [x] API keys are not printed in plaintext by helper scripts (masked output only)
- [ ] JWT secret loaded from environment (no hardcoded secrets)
- [ ] Database path / connection string loaded from environment where applicable

---

## Logging & Data Exposure
- [x] ScanEvent persistence stores domain only (no full URL or query parameters)
- [x] `/api/analyze-url` does not log request bodies
- [x] Authorization and X-API-Key headers are never logged
- [x] Normalized URLs returned to clients are sanitized and consistent

---

## CORS & Network Controls
- [x] CORS headers are explicitly allowlisted
  - Content-Type
  - Authorization
  - X-API-Key

---

## Authentication & Authorization
- [x] `/api/analyze-url` requires a valid API key
- [x] `/api/admin/*` endpoints require admin JWT authentication
- [ ] Role-based access control beyond admin/user (future)

---

## Known Gaps / Future Hardening
- Rate limiting on analyze endpoint
- API key rotation and expiration
- Audit logging for admin actions
- Production secret management (Vault / cloud secrets)

---

## Notes
This checklist is intended to be a living document and will evolve as LinkGuard
moves beyond MVP into broader production usage.
