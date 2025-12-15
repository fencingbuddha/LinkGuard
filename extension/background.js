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