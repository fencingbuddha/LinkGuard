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