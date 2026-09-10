/* ============================================
   AUTH GUARD — no chat_session_id means the user
   never went through login.html, send them back.
   ============================================ */
const CHAT_SESSION_ID = localStorage.getItem("docquery_chat_session_id");
const TOKEN = localStorage.getItem("docquery_token"); // null for guests

if (!CHAT_SESSION_ID) {
  window.location.href = "login.html";
}

const CONFIG = {
  UPLOAD_ENDPOINT: "/api/documents/upload",
  CHAT_ENDPOINT: "/chat",
};

const state = {
  documentReady: false,
};

/* ============================================
   DOM REFS
   ============================================ */
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const dropzoneText = document.getElementById("dropzone-text");
const dropzoneFilename = document.getElementById("dropzone-filename");
const uploadStatus = document.getElementById("upload-status");

const chatStatus = document.getElementById("chat-status");
const chatLog = document.getElementById("chat-log");
const chatEmpty = document.getElementById("chat-empty");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");

const accountPill = document.getElementById("account-pill");
const logoutBtn = document.getElementById("logout-btn");

accountPill.textContent = TOKEN ? "Logged in" : "Guest session";
logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("docquery_token");
  localStorage.removeItem("docquery_chat_session_id");
  window.location.href = "index.html";
});

function authHeaders(extra = {}) {
  return TOKEN ? { ...extra, Authorization: `Bearer ${TOKEN}` } : extra;
}

/* ============================================
   UPLOAD
   ============================================ */
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("is-dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("is-dragover");
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) handleFile(file);
});

async function handleFile(file) {
  if (file.type !== "application/pdf") {
    showUploadStatus("Please choose a PDF file.", true);
    return;
  }

  dropzoneFilename.textContent = file.name;
  dropzoneText.textContent = "Uploading…";
  showUploadStatus("", false);

  const formData = new FormData();
  formData.append("file", file);
  formData.append("chat_session_id", CHAT_SESSION_ID);

  try {
    const res = await fetch(CONFIG.UPLOAD_ENDPOINT, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Upload failed (${res.status})`);

    state.documentReady = true;
    dropzoneText.textContent = "Tap to add another PDF to this chat";
    showUploadStatus(`"${file.name}" is indexed and ready.`, false);
    enableChat();
  } catch (err) {
    console.error(err);
    dropzoneText.textContent = "Tap to choose a PDF, or drag one in";
    showUploadStatus(err.message || "Couldn't upload that file.", true);
  }
}

function showUploadStatus(message, isError) {
  uploadStatus.textContent = message;
  uploadStatus.hidden = !message;
  uploadStatus.classList.toggle("is-error", isError);
}

function enableChat() {
  chatStatus.textContent = "Ready";
  chatStatus.classList.add("is-ready");
  chatInput.disabled = false;
  chatSend.disabled = false;
  chatInput.focus();
}

/* ============================================
   CHAT — manual SSE parsing over fetch()
   ============================================ */
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message || !state.documentReady) return;

  chatInput.value = "";
  appendMessage("user", message);
  const assistantEl = appendMessage("assistant", "", { streaming: true });

  chatInput.disabled = true;
  chatSend.disabled = true;

  try {
    await streamAnswer(message, assistantEl);
  } catch (err) {
    console.error(err);
    setMessageText(assistantEl, "Something went wrong reaching the backend.");
  } finally {
    stopStreamingCursor(assistantEl);
    chatInput.disabled = false;
    chatSend.disabled = false;
    chatInput.focus();
  }
});

async function streamAnswer(message, assistantEl) {
  const res = await fetch(CONFIG.CHAT_ENDPOINT, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      chat_session_id: CHAT_SESSION_ID,
      question: message,
    }),
  });

  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answerText = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop();

    for (const part of parts) {
      const { event, data } = parseSSEEvent(part);
      if (!event || data === null) continue;

      let payload;
      try { payload = JSON.parse(data); } catch { continue; }

      if (event === "token") {
        answerText += payload.content ?? "";
        setMessageText(assistantEl, answerText, { streaming: true });
      } else if (event === "sources") {
        renderSourceChips(assistantEl, payload.sources ?? []);
      } else if (event === "error") {
        setMessageText(assistantEl, payload.message || "The assistant couldn't answer that.");
      }
    }
  }
}

function parseSSEEvent(rawBlock) {
  let event = null;
  let data = null;
  rawBlock.split("\n").forEach((line) => {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data = line.slice(5).trim();
  });
  return { event, data };
}

/* ============================================
   CHAT DOM HELPERS
   ============================================ */
function appendMessage(role, text, opts = {}) {
  chatEmpty.hidden = true;
  const el = document.createElement("div");
  el.className = `chat-message ${role}`;
  el.innerHTML = escapeHtml(text) + (opts.streaming ? '<span class="cursor"></span>' : "");
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}

function setMessageText(el, text, opts = {}) {
  el.innerHTML = escapeHtml(text) + (opts.streaming ? '<span class="cursor"></span>' : "");
  chatLog.scrollTop = chatLog.scrollHeight;
}

function stopStreamingCursor(el) {
  const cursor = el.querySelector(".cursor");
  if (cursor) cursor.remove();
}

function renderSourceChips(el, sources) {
  const wrap = document.createElement("div");
  wrap.className = "source-chips";
  sources.forEach((s) => {
    const chip = document.createElement("span");
    chip.className = "source-chip";
    chip.textContent = s.page ? `${s.source} · p.${s.page}` : s.source;
    wrap.appendChild(chip);
  });
  el.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}