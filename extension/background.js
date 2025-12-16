async function getConfig() {
  const { backendUrl = "", apiKey = "" } = await chrome.storage.local.get([
    "backendUrl",
    "apiKey",
  ]);
  return { backendUrl, apiKey };
}

function _trimTrailingSlashes(s) {
  return (s || "").replace(/\/+$/, "");
}

// --- Decision memory (session-based) ---
// Stores user decisions per normalized hostname for the current browser session.
// MV3 supports chrome.storage.session; we fall back to an in-memory Map if unavailable.

const _decisionMem = new Map(); // fallback only

function _getSessionStorage() {
  // chrome.storage.session may be unavailable in some contexts / older Chrome
  return chrome?.storage?.session;
}

function _normalizeDecisionKey(inputUrl) {
  try {
    const u = new URL(inputUrl);
    // Normalize to hostname only (e.g., iana.org)
    return (u.hostname || "").toLowerCase();
  } catch {
    return "";
  }
}

async function getDecisionForUrl(url) {
  const key = _normalizeDecisionKey(url);
  if (!key) return { key: "", decision: null };

  const session = _getSessionStorage();
  if (session) {
    const data = await session.get([key]);
    const decision = data?.[key] ?? null;
    return { key, decision };
  }

  return { key, decision: _decisionMem.get(key) ?? null };
}

async function setDecisionForKey(key, decision) {
  const normalizedKey = (key || "").toLowerCase().trim();
  if (!normalizedKey) return { ok: false };

  const session = _getSessionStorage();
  if (session) {
    await session.set({ [normalizedKey]: decision });
    return { ok: true };
  }

  _decisionMem.set(normalizedKey, decision);
  return { ok: true };
}

async function analyzeUrlViaBackend(url) {
  const { backendUrl, apiKey } = await getConfig();

  if (!backendUrl) {
    return {
      ok: false,
      error: "MISSING_BACKEND_URL",
      message: "Backend URL is not configured.",
    };
  }

  if (!apiKey) {
    return {
      ok: false,
      error: "MISSING_API_KEY",
      message: "API key is not configured.",
    };
  }

  const endpoint = `${_trimTrailingSlashes(backendUrl)}/api/analyze-url`;

  try {
    console.log("[LinkGuard] Request ->", endpoint, { url });

    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ url }),
    });

    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      // leave as null; some errors may not be JSON
    }

    if (!res.ok) {
      console.warn("[LinkGuard] Error <-", res.status, data ?? text);
      return {
        ok: false,
        error: "HTTP_ERROR",
        status: res.status,
        message:
          (data && (data.detail || data.message)) ||
          `Backend returned ${res.status}`,
        raw: data ?? text,
      };
    }

    console.log("[LinkGuard] Response <-", data);
    return { ok: true, result: data };
  } catch (err) {
    console.error("[LinkGuard] Network error", err);
    return {
      ok: false,
      error: "NETWORK_ERROR",
      message: String(err),
    };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PING") {
    sendResponse({ ok: true, from: "background", ts: Date.now() });
    return true;
  }

  if (message?.type === "GET_CONFIG") {
    getConfig().then((cfg) => sendResponse({ ok: true, cfg }));
    return true; // async response
  }

  if (message?.type === "GET_DECISION") {
    const url = message?.url;

    getDecisionForUrl(url).then(({ key, decision }) => {
      sendResponse({ ok: true, key, decision });
    });

    return true; // async response
  }

  if (message?.type === "SET_DECISION") {
    const key = message?.key;
    const decision = message?.decision; // expected: "ALLOW" | "BLOCK"

    setDecisionForKey(key, decision).then((r) => {
      sendResponse({ ok: true, ...r });
    });

    return true; // async response
  }

  if (message?.type === "ANALYZE_URL") {
    const url = message?.url;

    // Defensive logging for traceability.
    console.log(
      "[LinkGuard] ANALYZE_URL received:",
      url,
      "from tab:",
      sender?.tab?.url
    );

    analyzeUrlViaBackend(url).then((payload) => sendResponse(payload));
    return true; // async response
  }

  // Unknown message type: ignore.
  return false;
});