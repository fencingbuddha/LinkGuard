async function getConfig() {
  // Support multiple key names so Options UI and background stay in sync even if
  // we changed naming during development.
  const data = await chrome.storage.local.get([
    "backendUrl",
    "apiKey",
    "backend_url",
    "api_key",
    "BACKEND_URL",
    "API_KEY",
    "LG_BACKEND_URL",
    "LG_API_KEY",
  ]);

  const backendUrl = String(
    data.backendUrl ?? data.backend_url ?? data.BACKEND_URL ?? data.LG_BACKEND_URL ?? ""
  ).trim();

  const apiKey = String(
    data.apiKey ?? data.api_key ?? data.API_KEY ?? data.LG_API_KEY ?? ""
  ).trim();

  return { backendUrl, apiKey };
}

function _trimTrailingSlashes(s) {
  return (s || "").replace(/\/+$/, "");
}

// --- Config fingerprinting ---
// If the user changes backend URL / API key during testing, any per-domain session decision
// should be invalidated so we don't silently bypass analysis with a stale ALLOW.

const _CFG_FINGERPRINT_KEY = "__lg_cfg_fingerprint";
const _AUTH_INVALID_KEY = "__lg_auth_invalid";

function _cfgFingerprint(cfg) {
  const b = (cfg?.backendUrl || "").trim();
  const k = (cfg?.apiKey || "").trim();
  return `${b}::${k}`;
}

async function _ensureConfigFingerprint(flowId) {
  const cfg = await getConfig();
  const fp = _cfgFingerprint(cfg);

  const session = _getSessionStorage();
  if (!session) {
    // If we don't have session storage, we can only clear the in-memory map
    // when config changes. Track last fp in a global.
    if (typeof self.__lg_last_fp === "string" && self.__lg_last_fp !== fp) {
      _decisionMem.clear();
      logEvent("decision_cache_cleared", {
        level: "warn",
        flow_id: flowId || null,
        reason: "CONFIG_CHANGED",
      });
    }
    self.__lg_last_fp = fp;
    return;
  }

  const data = await session.get([_CFG_FINGERPRINT_KEY]);
  const prev = data?.[_CFG_FINGERPRINT_KEY] ?? null;

  if (prev && prev !== fp) {
    // Clear all per-domain decisions for this session to force re-analysis.
    await session.clear();
    logEvent("decision_cache_cleared", {
      level: "warn",
      flow_id: flowId || null,
      reason: "CONFIG_CHANGED",
    });
  }

  // Re-set fingerprint after any clear.
  await session.set({ [_CFG_FINGERPRINT_KEY]: fp });
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

// --- Make background failures visible (Issue #58 debugging aid) ---
// MV3 service workers can fail quietly; capture uncaught errors so we can see why
// analysis isn't reaching the backend.
self.addEventListener("unhandledrejection", (e) => {
  try {
    logEvent("bg_unhandledrejection", {
      level: "error",
      message: String(e?.reason || e),
    });
  } catch {
    console.error("[LinkGuard][bg] unhandledrejection", e?.reason || e);
  }
});

self.addEventListener("error", (e) => {
  try {
    logEvent("bg_error", {
      level: "error",
      message: String(e?.message || e),
    });
  } catch {
    console.error("[LinkGuard][bg] error", e?.message || e);
  }
});

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
    const flags = await session.get([_AUTH_INVALID_KEY]);
    if (flags?.[_AUTH_INVALID_KEY]) {
      // Hard-block all traffic when the backend auth/config is known-bad.
      return { key, decision: null, reason: "AUTH_INVALID" };
    }
  }

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

  // If config changed since the last click, invalidate any cached session decisions.
  await _ensureConfigFingerprint(flowId);

  {
    const session = _getSessionStorage();
    if (session) {
      const flags = await session.get([_AUTH_INVALID_KEY]);
        if (flags?.[_AUTH_INVALID_KEY]) {
        const endpoint = backendUrl ? `${_trimTrailingSlashes(backendUrl)}/api/analyze-url` : "";

        logEvent("fallback_not_configured", {
          level: "warn",
          flow_id: flowId || null,
          reason: "AUTH_ERROR",
          status: 401,
          endpoint,
        });

        return {
          ok: false,
          error: "AUTH_ERROR",
          status: 401,
          message: "Invalid API key",
          notice: {
            code: "AUTH_INVALID",
            message: "LinkGuard is misconfigured (invalid API key) — contact IT",
          },
        };
      }
    }
  }

  logEvent("config_loaded", {
    flow_id: flowId || null,
    has_backend_url: Boolean(backendUrl),
    has_api_key: Boolean(apiKey),
    backend_url_preview: backendUrl ? `${backendUrl.slice(0, 40)}${backendUrl.length > 40 ? "…" : ""}` : "",
    api_key_prefix: apiKey ? `${apiKey.slice(0, 6)}…` : "",
  });

  if (!backendUrl) {
    logEvent("fallback_not_configured", {
      level: "warn",
      flow_id: flowId || null,
      reason: "MISSING_BACKEND_URL",
    });

    return {
      ok: false,
      error: "MISSING_BACKEND_URL",
      message: "Backend URL is not configured.",
      notice: {
        code: "NOT_CONFIGURED",
        message: "LinkGuard isn’t configured yet — contact IT",
      },
    };
  }

  if (!apiKey) {
    logEvent("fallback_not_configured", {
      level: "warn",
      flow_id: flowId || null,
      reason: "MISSING_API_KEY",
      backend_url_preview: backendUrl ? `${backendUrl.slice(0, 40)}${backendUrl.length > 40 ? "…" : ""}` : "",
    });

    return {
      ok: false,
      error: "MISSING_API_KEY",
      message: "API key is not configured.",
      notice: {
        code: "NOT_CONFIGURED",
        message: "LinkGuard isn’t configured yet — contact IT",
      },
    };
  }

  const endpoint = `${_trimTrailingSlashes(backendUrl)}/api/analyze-url`;

  logEvent("analyze_request", {
    flow_id: flowId || null,
    url,
    domain: _safeDomainFromUrl(url),
    endpoint,
  });

  logEvent("fetch_start", {
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

    logEvent("fetch_done", {
      flow_id: flowId || null,
      url,
      domain: _safeDomainFromUrl(url),
      endpoint,
      status: res.status,
      ok: res.ok,
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
      // Safe-fallback on auth/config errors: do NOT block browsing.
      // Content script can show a single non-scary notice.
      const status = res.status;
      const isAuthOrConfigError = status === 401 || status === 403;

      if (isAuthOrConfigError) {
        logEvent("fallback_not_configured", {
          level: "warn",
          flow_id: flowId || null,
          reason: "AUTH_ERROR",
          status,
          endpoint,
        });
        {
          const session = _getSessionStorage();
          if (session) {
            await session.set({ [_AUTH_INVALID_KEY]: true });
          } else {
            // Fallback: clear any in-memory decisions so we don't silently allow.
            _decisionMem.clear();
          }
        }
        return {
          ok: false,
          error: "AUTH_ERROR",
          status,
          message: (data && (data.detail || data.message)) || "Invalid API key",
          notice: {
            code: "AUTH_INVALID",
            message: "LinkGuard is misconfigured (invalid API key) — contact IT",
          },
          raw: data ?? text,
        };
      }
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

    (async () => {
      await _ensureConfigFingerprint(message?.flowId || null);
      const { key, decision } = await getDecisionForUrl(url);
      sendResponse({ ok: true, key, decision });
    })();

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