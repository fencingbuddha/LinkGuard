# LinkGuard – Developer Setup Guide

This guide walks a developer through running the LinkGuard backend and loading the Chrome extension locally for development and testing.

---

## Prerequisites

Before starting, ensure you have the following:

- Google Chrome (latest stable recommended)
- Python 3.10+ installed
- Node.js (only required if building frontend assets later)
- Git
- Access to the LinkGuard repository
- A terminal (macOS, Linux, or Windows)

---

## Backend Setup

### 1. Create and activate a virtual environment

From the backend directory:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate   # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the backend directory (or export variables manually):

```env
API_KEY=your_api_key_here
```

> The API key is required by the extension to authenticate requests to the backend.

### 4. Start the backend server

```bash
uvicorn app.main:app --reload
```

The backend should now be running at:

```
http://localhost:8000
```

To verify, open the URL in a browser or run:

```bash
curl http://localhost:8000/health
```

---

## Chrome Extension Setup

### 1. Open Chrome Extensions page

Navigate to:

```
chrome://extensions
```

Enable **Developer mode** (top right).

### 2. Load the extension

Click **Load unpacked** and select the extension directory (the folder containing `manifest.json`).

The LinkGuard extension should now appear in the list of installed extensions.

---

## Extension Configuration

### 1. Open extension options

Click the LinkGuard extension icon and open **Options** (or use the Extensions page).

### 2. Configure backend settings

Set the following values:

- **Backend URL:** `http://localhost:8000`
- **API Key:** The same API key configured in the backend

Save the settings.

---

## End-to-End Validation

### Test SAFE link behavior

1. Navigate to a known SAFE site (e.g. `https://example.com`)
2. Click a standard link
3. Expected result: navigation proceeds without interruption

### Test SUSPICIOUS / DANGEROUS behavior

1. Use the dev test hook (e.g. `?linkguard_test=suspicious`)
2. Click the test link
3. Expected result:
   - Warning overlay appears
   - User can choose **Go Back** or **Proceed Anyway**
   - Decision memory persists for the browser session

---

## Troubleshooting

- **Extension not triggering:** Confirm the backend is running and reachable
- **401 / auth errors:** Verify the API key matches on both sides
- **No overlay shown:** Check Chrome DevTools console for LinkGuard logs

---

## Done

At this point, you should have:

- A running backend
- The LinkGuard extension loaded in Chrome
- Successful SAFE and SUSPICIOUS link validation

You are now ready to develop, debug, or extend LinkGuard.
