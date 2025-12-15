(async () => {
  try {
    const res = await chrome.runtime.sendMessage({ type: "PING" });
    console.log("LinkGuard content script ping response:", res);
  } catch (e) {
    console.warn("LinkGuard ping failed:", e);
  }
})();