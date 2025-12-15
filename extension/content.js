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

      // Background now returns: { ok: boolean, result?: {...}, error?: string, ... }
      if (!res?.ok) {
        console.warn("LinkGuard analysis failed; allowing navigation:", url, res);
        window.location.assign(url); // fail-open for MVP
        return;
      }

      const result = res.result || {};
      const riskCategory = String(result.risk_category || "").toUpperCase();

      console.log("LinkGuard analysis result:", { url, riskCategory, result });

      // MVP policy: block only HIGH; allow everything else.
      if (riskCategory === "HIGH") {
        const explanation = Array.isArray(result.explanations)
          ? result.explanations.join("\n")
          : result.explanation || "(no details)";

        alert(
          `LinkGuard blocked a high-risk link:\n\n${url}\n\nReason:\n${explanation}`
        );
        return;
      }

      window.location.assign(url);
    } catch (err) {
      // Fail-open for now (don’t break the web)
      console.warn("LinkGuard error; allowing navigation:", err);
      window.location.assign(url);
    }
  },
  true // capture
);