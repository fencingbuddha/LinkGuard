chrome.runtime.onInstalled.addListener(() => {
  console.log("LinkGuard installed");
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PING") {
    sendResponse({ ok: true, from: "background", ts: Date.now() });
    return true;
  }
});