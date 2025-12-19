function findAnchor(el) {
  return el?.closest ? el.closest("a[href]") : null;
}

function isModifiedClick(e) {
  return e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0;
}

function normalizeDecisionKey(urlString) {
  try {
    const u = new URL(urlString);
    // Hostname is stable and good enough for MVP decision memory.
    return (u.hostname || "").toLowerCase();
  } catch {
    return null;
  }
}

// --- Structured event logging (Issue #37) ---
const LG_LOG = true;

function lgFlowId() {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}

function lgDomain(urlString) {
  try {
    return new URL(urlString).hostname.toLowerCase();
  } catch {
    return null;
  }
}

function lgLog(event, data = {}) {
  if (!LG_LOG) return;
  const payload = {
    app: "linkguard",
    v: 1,
    ts: new Date().toISOString(),
    scope: "content",
    event,
    ...data,
  };
  // Keep a consistent prefix for easy filtering.
  console.log("[LinkGuard]", payload);
}

function lgError(reason, data = {}) {
  if (!LG_LOG) return;
  lgLog("error", { reason, ...data });
}

async function getDecisionForUrl(urlString, flowId) {
  const fallbackKey = normalizeDecisionKey(urlString);
  if (!fallbackKey) return { key: null, decision: null };

  try {
    // Background expects { type: "GET_DECISION", url }
    const res = await chrome.runtime.sendMessage({
      type: "GET_DECISION",
      url: urlString,
      flowId: flowId || null,
    });

    return {
      key: res?.key || fallbackKey,
      decision: res?.decision ?? null,
    };
  } catch {
    return { key: fallbackKey, decision: null };
  }
}

async function setDecisionForKey(key, decision, flowId) {
  if (!key) return;
  try {
    await chrome.runtime.sendMessage({
      type: "SET_DECISION",
      key,
      decision,
      flowId: flowId || null,
    });
  } catch {
    // ignore for MVP
  }
}

function getUxPolicyForRisk(riskCategoryRaw) {
  const risk = String(riskCategoryRaw || "").toUpperCase();

  // UX tiers: SAFE / LOW / MEDIUM / HIGH
  // Backend currently uses: SAFE / SUSPICIOUS / DANGEROUS / HIGH (and may expand later).
  if (risk === "SAFE") {
    return { tier: "SAFE", action: "ALLOW", displayRisk: "SAFE" };
  }

  // Treat SUSPICIOUS as MEDIUM for MVP: show overlay with proceed/cancel.
  if (risk === "SUSPICIOUS") {
    return { tier: "MEDIUM", action: "OVERLAY", displayRisk: "SUSPICIOUS" };
  }

  // Treat DANGEROUS/HIGH as HIGH for MVP: show overlay labeled DANGEROUS.
  if (risk === "DANGEROUS" || risk === "HIGH") {
    return { tier: "HIGH", action: "OVERLAY", displayRisk: "DANGEROUS" };
  }

  // Unknown category: fail-open for MVP.
  return { tier: "UNKNOWN", action: "ALLOW", displayRisk: "SAFE" };
}

function showWarningOverlay({ url, riskCategory, explanation, onProceed, onCancel }) {
  const existing = document.getElementById("linkguard-warning-overlay");
  if (existing) existing.remove();

  const overlay = document.createElement("div");
  overlay.id = "linkguard-warning-overlay";
  overlay.style.position = "fixed";
  overlay.style.top = "0";
  overlay.style.left = "0";
  overlay.style.width = "100vw";
  overlay.style.height = "100vh";
  // Darker backdrop for readability
  overlay.style.background = "rgba(0, 0, 0, 0.72)";
  overlay.style.zIndex = "2147483647";
  overlay.style.display = "flex";
  overlay.style.alignItems = "center";
  overlay.style.justifyContent = "center";
  overlay.style.padding = "24px";

  const card = document.createElement("div");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");
  card.style.background = "#1f1f1f";
  card.style.color = "#fff";
  card.style.padding = "24px";
  card.style.borderRadius = "12px";
  card.style.maxWidth = "640px";
  card.style.width = "100%";
  card.style.fontFamily =
    "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  card.style.boxShadow = "0 18px 60px rgba(0,0,0,0.7)";
  card.style.backdropFilter = "blur(7px)";
  card.style.border = "1px solid rgba(255,255,255,0.12)";

  const header = document.createElement("div");
  header.style.display = "flex";
  header.style.alignItems = "center";
  header.style.justifyContent = "space-between";
  header.style.gap = "12px";

  const titleWrap = document.createElement("div");

  const title = document.createElement("h2");
  title.textContent =
    riskCategory === "DANGEROUS" ? "This link may be dangerous" : "This link looks suspicious";
  title.style.margin = "0";
  title.style.fontSize = "28px";
  title.style.lineHeight = "1.2";

  const badge = document.createElement("div");
  badge.textContent = riskCategory;
  badge.style.padding = "6px 10px";
  badge.style.borderRadius = "999px";
  badge.style.fontSize = "12px";
  badge.style.fontWeight = "700";
  badge.style.letterSpacing = "0.08em";
  badge.style.border = "1px solid rgba(255,255,255,0.18)";
  badge.style.background =
    riskCategory === "DANGEROUS" ? "rgba(192, 57, 43, 0.28)" : "rgba(241, 196, 15, 0.22)";

  titleWrap.appendChild(title);

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.textContent = "×";
  closeBtn.setAttribute("aria-label", "Close warning");
  closeBtn.style.background = "transparent";
  closeBtn.style.border = "1px solid rgba(255,255,255,0.18)";
  closeBtn.style.color = "#fff";
  closeBtn.style.width = "40px";
  closeBtn.style.height = "40px";
  closeBtn.style.borderRadius = "10px";
  closeBtn.style.cursor = "pointer";
  closeBtn.style.fontSize = "22px";
  closeBtn.style.lineHeight = "1";

  header.appendChild(titleWrap);
  header.appendChild(badge);
  header.appendChild(closeBtn);

  const urlLabel = document.createElement("div");
  urlLabel.textContent = "Destination";
  urlLabel.style.marginTop = "18px";
  urlLabel.style.marginBottom = "8px";
  urlLabel.style.fontSize = "13px";
  urlLabel.style.opacity = "0.85";

  const urlEl = document.createElement("pre");
  urlEl.textContent = url;
  urlEl.style.whiteSpace = "pre-wrap";
  urlEl.style.wordBreak = "break-all";
  urlEl.style.background = "#0f0f0f";
  urlEl.style.padding = "14px";
  urlEl.style.borderRadius = "10px";
  urlEl.style.border = "1px solid rgba(255,255,255,0.12)";
  urlEl.style.margin = "0";
  urlEl.style.fontSize = "14px";

  const explanationEl = document.createElement("p");
  explanationEl.textContent = explanation || "No additional details provided.";
  explanationEl.style.marginTop = "14px";
  explanationEl.style.marginBottom = "0";
  explanationEl.style.opacity = "0.92";

  const actions = document.createElement("div");
  actions.style.display = "flex";
  actions.style.justifyContent = "flex-end";
  actions.style.gap = "12px";
  actions.style.marginTop = "20px";

  const baseBtn = (btn) => {
    btn.type = "button";
    btn.style.padding = "10px 14px";
    btn.style.borderRadius = "10px";
    btn.style.cursor = "pointer";
    btn.style.fontWeight = "600";
    btn.style.border = "1px solid rgba(255,255,255,0.18)";
    btn.style.background = "#2a2a2a";
    btn.style.color = "#fff";
  };

  const backBtn = document.createElement("button");
  backBtn.textContent = "Go Back";
  baseBtn(backBtn);

  const proceedBtn = document.createElement("button");
  proceedBtn.textContent = "Proceed Anyway";
  baseBtn(proceedBtn);
  proceedBtn.style.background = riskCategory === "DANGEROUS" ? "#c0392b" : "#b9770e";
  proceedBtn.style.border = "none";

  // Close helpers
  const cleanupAndCancel = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKeyDown, true);
    onCancel && onCancel();
  };

  const cleanupAndProceed = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKeyDown, true);
    onProceed && onProceed();
  };

  const onKeyDown = (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      cleanupAndCancel();
    }
  };

  closeBtn.onclick = cleanupAndCancel;
  backBtn.onclick = cleanupAndCancel;
  proceedBtn.onclick = cleanupAndProceed;

  // Click outside the card cancels
  overlay.addEventListener("click", (ev) => {
    if (ev.target === overlay) cleanupAndCancel();
  });

  // Prevent click-through inside the card
  card.addEventListener("click", (ev) => ev.stopPropagation());

  actions.appendChild(backBtn);
  actions.appendChild(proceedBtn);

  card.appendChild(header);
  card.appendChild(urlLabel);
  card.appendChild(urlEl);
  card.appendChild(explanationEl);
  card.appendChild(actions);

  overlay.appendChild(card);
  document.body.appendChild(overlay);

  // Enable ESC to close
  document.addEventListener("keydown", onKeyDown, true);

  // Focus for accessibility / keyboard
  setTimeout(() => {
    try {
      proceedBtn.focus();
    } catch {
      // ignore
    }
  }, 0);
}

document.addEventListener(
  "click",
  async (e) => {
    if (isModifiedClick(e)) return;

    const a = findAnchor(e.target);
    if (!a) return;

    // Use the resolved destination URL (not the current page URL)
    const url = a.href;
    if (!url) return;

    // Ignore non-http(s) navigation and in-page anchors
    if (url.startsWith("#") || url.startsWith("javascript:")) return;
    if (!url.startsWith("http://") && !url.startsWith("https://")) return;

    // Don't interfere with new-tab behavior
    const target = (a.getAttribute("target") || "").toLowerCase();
    if (target === "_blank") return;

    // Block navigation while we ask background
    e.preventDefault();
    // Stronger than stopPropagation() to prevent page handlers from navigating.
    e.stopImmediatePropagation();

    const flow_id = lgFlowId();
    const domain = lgDomain(url) || undefined;

    lgLog("click_intercepted", { flow_id, url, domain });

    // Decision memory (session-based): if user already chose allow/block for this domain,
    // respect it without prompting again.
    const { key: decisionKey, decision } = await getDecisionForUrl(url, flow_id);

    if (decision === "ALLOW") {
      lgLog("decision_applied", {
        flow_id,
        url,
        domain,
        decision: "ALLOW",
        reason: "decision_memory",
        key: decisionKey || undefined,
      });
      window.location.assign(url);
      return;
    }

    if (decision === "BLOCK") {
      lgLog("decision_applied", {
        flow_id,
        url,
        domain,
        decision: "BLOCK",
        reason: "decision_memory",
        key: decisionKey || undefined,
      });
      // Stay on page; do not navigate.
      return;
    }

    try {
      lgLog("analyze_request", { flow_id, url, domain });
      const res = await chrome.runtime.sendMessage({
        type: "ANALYZE_URL",
        url,
        flowId: flow_id,
      });

      // Background now returns: { ok: boolean, result?: {...}, error?: string, ... }
      if (!res?.ok) {
        // Treat failures as fail-open, but do not cache a decision.
        lgError("analysis_failed_fail_open", {
          flow_id,
          url,
          domain,
          extra: { response: res },
        });
        window.location.assign(url); // fail-open for MVP
        return;
      }

      const result = res.result || {};
      const riskCategory = String(result.risk_category || "").toUpperCase();

      lgLog("analysis_result", {
        flow_id,
        url,
        domain,
        risk_category: riskCategory || "UNKNOWN",
      });

      const explanation = Array.isArray(result.explanations)
        ? result.explanations.join("\n")
        : result.explanation || "(no details)";

      // Centralized Risk → UX policy mapping
      const policy = getUxPolicyForRisk(riskCategory);

      if (policy.action === "ALLOW") {
        // SAFE/UNKNOWN: navigate immediately (fail-open for MVP)
        lgLog("navigation", {
          flow_id,
          url,
          domain,
          decision: "ALLOW",
          reason: policy.tier === "SAFE" ? "safe_allow" : "unknown_fail_open",
        });
        window.location.assign(url);
        return;
      }

      // Overlay (MEDIUM/HIGH): show warning and let user choose
      lgLog("overlay_shown", {
        flow_id,
        url,
        domain,
        risk_category: policy.displayRisk,
      });

      showWarningOverlay({
        url,
        riskCategory: policy.displayRisk,
        explanation,
        onProceed: async () => {
          lgLog("user_decision", {
            flow_id,
            url,
            domain,
            decision: "ALLOW",
            reason: "user_override",
            key: decisionKey || undefined,
          });
          // Cache allow for this domain for the current browser session.
          if (decisionKey) await setDecisionForKey(decisionKey, "ALLOW", flow_id);
          window.location.assign(url);
        },
        onCancel: async () => {
          lgLog("user_decision", {
            flow_id,
            url,
            domain,
            decision: "BLOCK",
            reason: "user_override",
            key: decisionKey || undefined,
          });
          // Cache block for this domain for the current browser session.
          if (decisionKey) await setDecisionForKey(decisionKey, "BLOCK", flow_id);
          // stay on the current page; overlay is removed in the helper
        },
      });
      return;
    } catch (err) {
      // Fail-open for now (don’t break the web)
      lgError("exception_fail_open", {
        flow_id,
        url,
        domain,
        extra: { message: String(err?.message || err) },
      });
      window.location.assign(url);
    }
  },
  true // capture
);