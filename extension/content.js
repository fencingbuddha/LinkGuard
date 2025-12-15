function findAnchor(el) {
  return el?.closest ? el.closest("a[href]") : null;
}

function isModifiedClick(e) {
  return e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0;
}

document.addEventListener(
  "click",
  async (e) => {
    if (isModifiedClick(e)) return;

    const a = findAnchor(e.target);
    if (!a) return;

    const href = a.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;

    // Don't interfere with new-tab behavior
    const target = (a.getAttribute("target") || "").toLowerCase();
    if (target === "_blank") return;

    let url;
    try {
      url = new URL(href, window.location.href).toString();
    } catch {
      return;
    }

    // Block navigation while we ask background
    e.preventDefault();
    e.stopPropagation();

    console.log("LinkGuard intercepted click:", url);

    try {
      const res = await chrome.runtime.sendMessage({ type: "ANALYZE_URL", url });

      // MVP behavior: allow immediately if background says ALLOW
      if (res?.decision === "ALLOW") {
        window.location.assign(url);
      } else {
        console.warn("LinkGuard blocked navigation:", url, res);
      }
    } catch (err) {
      // Fail-open for now (don’t break the web)
      console.warn("LinkGuard error; allowing navigation:", err);
      window.location.assign(url);
    }
  },
  true // capture
);