# LinkGuard Extension — Manual Test Plan (MVP)

## Scope
Manual regression checklist for the Chrome MV3 extension + backend `/api/analyze-url`.

## Test Environment / Setup
- Chrome (MV3 supported)
- LinkGuard extension loaded via `chrome://extensions` → **Developer mode** → **Load unpacked**
- Backend running locally (default): `http://localhost:8000`
- Backend has an ACTIVE API key in DB
- Extension has values set in `chrome.storage.local`:
  - `backendUrl` = `http://localhost:8000`
  - `apiKey` = `<valid key>`

### Helpful dev URLs (safe)
- SAFE link: `https://iana.org/domains/example`
- Forced SUSPICIOUS (dev hook): `https://iana.org/domains/example?linkguard_test=suspicious`
- Forced DANGEROUS (dev hook): `https://iana.org/domains/example?linkguard_test=dangerous`

### Logging expectations
- Content + background logs are structured objects with a shared `flow_id`.
- Use DevTools for:
  - page tab (content logs)
  - extension service worker (background logs)

---

## TC-01 Valid configuration: SAFE link allows navigation
**Preconditions**
- Backend running
- Valid API key configured
- Decision memory cleared (restart browser or clear session storage)

**Steps**
1. Open `https://example.com`
2. Click a link to `https://iana.org/domains/example` (or paste a page with that link)

**Expected**
- No overlay shown
- Navigation proceeds immediately
- Logs show:
  - `click_intercepted` → `analyze_request` → `analysis_result (SAFE)` → `navigation (ALLOW)`

---

## TC-02 Missing API key: backend returns 401 → fail-open
**Preconditions**
- Backend running
- Remove/blank `apiKey` in `chrome.storage.local`

**Steps**
1. Click any valid link (SAFE is fine)

**Expected**
- Extension receives error/missing key handling
- Navigation still proceeds (fail-open MVP behavior)
- Logs show an error event indicating missing/invalid key (401) and a fail-open navigation

---

## TC-03 Invalid API key: backend returns 401 → fail-open
**Preconditions**
- Backend running
- Set `apiKey` to a known-bad value

**Steps**
1. Click a link (SAFE is fine)

**Expected**
- Backend responds 401 invalid key
- Navigation proceeds (fail-open)
- Logs include `analysis_failed_fail_open` (or equivalent error event)

---

## TC-04 Backend unavailable (network error) → fail-open
**Preconditions**
- Stop backend server (or set backendUrl to a dead port)

**Steps**
1. Click a link

**Expected**
- Extension logs fetch/network failure
- Navigation proceeds (fail-open)
- No overlay (since analysis didn’t complete)

---

## TC-05 Forced SUSPICIOUS shows overlay and blocks by default
**Preconditions**
- Backend running
- Valid API key configured
- Decision memory cleared

**Steps**
1. Ensure you have a clickable link to:
   `https://iana.org/domains/example?linkguard_test=suspicious`
2. Click the link

**Expected**
- Warning overlay appears before navigation
- Overlay contains:
  - risk badge = `SUSPICIOUS`
  - destination URL
  - explanation text (dev hook message or backend explanation)
  - buttons: **Go Back** and **Proceed Anyway**
- Clicking outside card cancels
- ESC cancels
- Logs show `overlay_shown`

---

## TC-06 SUSPICIOUS: Proceed Anyway navigates + writes decision memory
**Preconditions**
- TC-05 overlay displayed

**Steps**
1. Click **Proceed Anyway**
2. Open a new tab (same browser session)
3. Click the same SUSPICIOUS link again

**Expected**
- First click navigates
- Second click does **not** show overlay (decision memory ALLOW)
- Logs show:
  - first run: `user_decision (ALLOW)` + `SET_DECISION`
  - second run: `decision_applied (ALLOW, decision_memory)`

---

## TC-07 SUSPICIOUS: Go Back blocks + writes decision memory
**Preconditions**
- Decision memory cleared

**Steps**
1. Click the SUSPICIOUS link
2. Click **Go Back**
3. Click the same SUSPICIOUS link again in the same session

**Expected**
- No navigation occurs
- Second click is auto-blocked (no overlay) due to decision memory BLOCK
- Logs show:
  - first run: `user_decision (BLOCK)` + `SET_DECISION`
  - second run: `decision_applied (BLOCK, decision_memory)`

---

## TC-08 Decision memory reset on browser restart
**Preconditions**
- You have an ALLOW or BLOCK decision cached in-session

**Steps**
1. Fully quit Chrome
2. Re-open Chrome
3. Click the SUSPICIOUS link again

**Expected**
- Overlay shows again (decision memory cleared for MVP session scope)

---

## TC-09 Forced DANGEROUS shows overlay (red styling) and blocks unless proceeded
**Preconditions**
- Backend running
- Valid API key configured
- Decision memory cleared

**Steps**
1. Click:
   `https://iana.org/domains/example?linkguard_test=dangerous`

**Expected**
- Overlay appears
- Risk badge indicates DANGEROUS
- Proceed button uses danger styling
- Go Back cancels and stays on page

---

## TC-10 Modified clicks are not intercepted
**Preconditions**
- Any page with a clickable link

**Steps**
1. Cmd+Click / Ctrl+Click a link
2. Middle-click a link
3. Shift+Click a link

**Expected**
- Extension does not block navigation or show overlay
- No LinkGuard click flow logs for those actions

---

## Acceptance Criteria Summary
- SAFE links navigate with no overlay
- SUSPICIOUS/DANGEROUS links always show overlay before navigation (unless decision memory applies)
- Proceed / Go Back behave correctly
- Backend failures (401/network) fail open (MVP)
- Logs are structured and correlated with `flow_id`