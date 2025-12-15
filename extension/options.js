const KEY_BACKEND_URL = "backendUrl";
const KEY_API_KEY = "apiKey";

const backendUrlEl = document.getElementById("backendUrl");
const apiKeyEl = document.getElementById("apiKey");
const saveBtn = document.getElementById("saveBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.style.color = isError ? "crimson" : "green";
  if (msg) setTimeout(() => (statusEl.textContent = ""), 2000);
}

function normalizeUrl(url) {
  if (!url) return "";
  // trim + remove trailing slash
  return url.trim().replace(/\/+$/, "");
}

async function loadSettings() {
  const data = await chrome.storage.local.get([KEY_BACKEND_URL, KEY_API_KEY]);
  backendUrlEl.value = data[KEY_BACKEND_URL] ?? "";
  apiKeyEl.value = data[KEY_API_KEY] ?? "";
}

async function saveSettings() {
  const backendUrl = normalizeUrl(backendUrlEl.value);
  const apiKey = apiKeyEl.value.trim();

  if (backendUrl && !/^https?:\/\//i.test(backendUrl)) {
    setStatus("Backend URL must start with http:// or https://", true);
    return;
  }

  await chrome.storage.local.set({
    [KEY_BACKEND_URL]: backendUrl,
    [KEY_API_KEY]: apiKey
  });

  setStatus("Saved");
}

async function clearSettings() {
  await chrome.storage.local.remove([KEY_BACKEND_URL, KEY_API_KEY]);
  backendUrlEl.value = "";
  apiKeyEl.value = "";
  setStatus("Cleared");
}

document.addEventListener("DOMContentLoaded", loadSettings);
saveBtn.addEventListener("click", saveSettings);
clearBtn.addEventListener("click", clearSettings);