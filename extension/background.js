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

// --- Structured event logging ---
// Background-side logs use a consistent event shape so they can be correlated with content.js.
// If content.js provides a `flowId`, we propagate it through logs + responses.

function _nowIso() {
  return new Date().toISOString();
}

function _safeDomainFromUrl(inputUrl) {
  try {
    return new URL(inputUrl).hostname.toLowerCase();
  } catch {
    return "";
  }
}

function logEvent(event, details = {}) {
  const payload = {
    app: "linkguard",
    layer: "background",
    event,
    ts: _nowIso(),
    ...details,
  };

  // Use console methods by severity, but always keep the same payload shape.
  const level = details?.level || "log";
  if (level === "warn") console.warn(payload);
  else if (level === "error") console.error(payload);
  else console.log(payload);
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

async function analyzeUrlViaBackend(url, flowId) {
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

  logEvent("analyze_request", {
    flow_id: flowId || null,
    url,
    domain: _safeDomainFromUrl(url),
    endpoint,
  });

  try {
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
      logEvent("analysis_error", {
        level: "warn",
        flow_id: flowId || null,
        url,
        domain: _safeDomainFromUrl(url),
        status: res.status,
        error: "HTTP_ERROR",
        message:
          (data && (data.detail || data.message)) ||
          `Backend returned ${res.status}`,
        raw: data ?? text,
      });
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

    // Normalize backend response shape so content.js can rely on `result.risk_category`.
    // Some backends may return `category` instead of `risk_category`.
    const normalized =
      data && typeof data === "object"
        ? {
            ...data,
            risk_category: data.risk_category ?? data.category ?? null,
            explanations: Array.isArray(data.explanations) ? data.explanations : [],
          }
        : {
            risk_category: null,
            explanations: [],
            raw: data ?? text,
          };

    logEvent("analysis_result", {
      flow_id: flowId || null,
      url,
      domain: _safeDomainFromUrl(url),
      risk_category: normalized?.risk_category ?? null,
      score: normalized?.score ?? null,
      result: normalized,
    });
    return { ok: true, result: normalized };
  } catch (err) {
    logEvent("analysis_error", {
      level: "error",
      flow_id: flowId || null,
      url,
      domain: _safeDomainFromUrl(url),
      error: "NETWORK_ERROR",
      message: String(err),
    });
    return {
      ok: false,
      error: "NETWORK_ERROR",
      message: String(err),
    };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PING") {
    logEvent("ping", { flow_id: message?.flowId || null, from_tab: sender?.tab?.url || null });
    sendResponse({ ok: true, from: "background", ts: Date.now() });
    return true;
  }

  if (message?.type === "GET_CONFIG") {
    logEvent("get_config", { flow_id: message?.flowId || null });
    getConfig().then((cfg) => sendResponse({ ok: true, cfg }));
    return true; // async response
  }

  if (message?.type === "GET_DECISION") {
    const url = message?.url;

    logEvent("decision_lookup", {
      flow_id: message?.flowId || null,
      url,
      domain: _safeDomainFromUrl(url),
    });

    getDecisionForUrl(url).then(({ key, decision }) => {
      sendResponse({ ok: true, key, decision });
    });

    return true; // async response
  }

  if (message?.type === "SET_DECISION") {
    const key = message?.key;
    const decision = message?.decision; // expected: "ALLOW" | "BLOCK"

    logEvent("decision_set", {
      flow_id: message?.flowId || null,
      key: (key || "").toLowerCase().trim(),
      decision: decision || null,
    });

    setDecisionForKey(key, decision).then((r) => {
      sendResponse({ ok: true, ...r });
    });

    return true; // async response
  }

  if (message?.type === "ANALYZE_URL") {
    const url = message?.url;
    const flowId = message?.flowId || null;

    logEvent("analyze_received", {
      flow_id: flowId,
      url,
      domain: _safeDomainFromUrl(url),
      from_tab: sender?.tab?.url || null,
    });

    analyzeUrlViaBackend(url, flowId).then((payload) => sendResponse({ ...payload, flowId }));
    return true; // async response
  }

  // Unknown message type: ignore.
  if (message?.type) {
    logEvent("unknown_message", { level: "warn", type: message.type });
  }
  return false;
});

// --- Toolbar behavior ---
// Clicking the extension icon should open the Options page (no popup UI).
// This is a quick demo-polish win and gives users a consistent entry point.

if (chrome?.action?.onClicked) {
  chrome.action.onClicked.addListener(() => {
    chrome.runtime.openOptionsPage();
    logEvent("toolbar_open_options", { ts: _nowIso() });
  });
}