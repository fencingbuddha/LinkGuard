async function getConfig() {
  const { backendUrl = "", apiKey = "" } = await chrome.storage.local.get(["backendUrl", "apiKey"]);
  return { backendUrl, apiKey };
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
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PING") {
    sendResponse({ ok: true, from: "background", ts: Date.now() });
    return true;
  }

  if (message?.type === "GET_CONFIG") {
    chrome.storage.local.get(["backendUrl", "apiKey"]).then((cfg) =>
      sendResponse({ ok: true, cfg })
    );
    return true;
  }

  if (message?.type === "ANALYZE_URL") {
    // MVP: just allow, but log what we captured.
    console.log("LinkGuard captured URL:", message.url, "from tab:", sender?.tab?.url);
    sendResponse({ ok: true, decision: "ALLOW" });
    return true;
  }
});