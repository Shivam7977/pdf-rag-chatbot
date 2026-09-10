const API_BASE = "";
let CHAT_SESSION_ID = localStorage.getItem("docquery_chat_session_id");
const TOKEN = localStorage.getItem("docquery_token");
const IS_GUEST_MODE = localStorage.getItem("docquery_guest_mode") === "true";

if (!TOKEN && !IS_GUEST_MODE) {
  window.location.href = "login.html";
}

const CONFIG = {
  UPLOAD_ENDPOINT: "/api/documents/upload",
  CHAT_ENDPOINT: "/chat",
};

const state = { documentReady: false };
let chatBeingDeleted = null;
let currentPreviewBlobUrl = null;

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

const sidebarChatList = document.getElementById("sidebar-chat-list");
const newChatBtn = document.getElementById("new-chat-btn");
const sidebarUserBtn = document.getElementById("sidebar-user-btn");
const sidebarUserMenu = document.getElementById("sidebar-user-menu");
const sidebarUserName = document.getElementById("sidebar-user-name");
const sidebarUserAvatar = document.getElementById("sidebar-user-avatar");

const documentsToggle = document.getElementById("documents-toggle");
const documentsPanel = document.getElementById("documents-panel");
const documentsList = document.getElementById("documents-list");

const deleteOverlay = document.getElementById("delete-confirm-overlay");
const deleteCancelBtn = document.getElementById("delete-cancel-btn");
const deleteConfirmBtn = document.getElementById("delete-confirm-btn");

const currentChatTitle = document.getElementById("current-chat-title");
const sidebar = document.getElementById("sidebar");
const sidebarCollapseBtn = document.getElementById("sidebar-collapse-btn");
const sidebarExpandBtn = document.getElementById("sidebar-expand-btn");

const previewOverlay = document.getElementById("preview-overlay");
const previewFilename = document.getElementById("preview-filename");
const previewIframe = document.getElementById("preview-iframe");
const previewDownloadBtn = document.getElementById("preview-download-btn");
const previewCloseBtn = document.getElementById("preview-close-btn");

function authHeaders(extra = {}) {
  return TOKEN ? { ...extra, Authorization: `Bearer ${TOKEN}` } : extra;
}

/* ============================================
   DOCUMENT PREVIEW MODAL
   ============================================ */
async function openDocumentPreview(filename) {
  previewFilename.textContent = filename;
  previewIframe.src = "";
  previewOverlay.hidden = false;

  try {
    const res = await fetch(
      API_BASE + `/chats/${CHAT_SESSION_ID}/documents/${encodeURIComponent(filename)}`,
      { headers: authHeaders() }
    );
    if (!res.ok) throw new Error("Couldn't load this document.");

    const blob = await res.blob();
    if (currentPreviewBlobUrl) URL.revokeObjectURL(currentPreviewBlobUrl);
    currentPreviewBlobUrl = URL.createObjectURL(blob);

    previewIframe.src = currentPreviewBlobUrl;
    previewDownloadBtn.href = currentPreviewBlobUrl;
    previewDownloadBtn.download = filename;
  } catch (err) {
    console.error(err);
    previewFilename.textContent = filename + " — failed to load";
  }
}

function closePreview() {
  previewOverlay.hidden = true;
  previewIframe.src = "";
  if (currentPreviewBlobUrl) {
    URL.revokeObjectURL(currentPreviewBlobUrl);
    currentPreviewBlobUrl = null;
  }
}

previewCloseBtn.addEventListener("click", closePreview);
previewOverlay.addEventListener("click", (e) => {
  if (e.target === previewOverlay) closePreview(); // click on the dark backdrop only
});

/* ============================================
   SIDEBAR COLLAPSE
   ============================================ */
sidebarCollapseBtn.addEventListener("click", () => {
  sidebar.classList.add("is-collapsed");
  sidebarExpandBtn.hidden = false;
});
sidebarExpandBtn.addEventListener("click", () => {
  sidebar.classList.remove("is-collapsed");
  sidebarExpandBtn.hidden = true;
});

/* ============================================
   CLICK-OUTSIDE-TO-CLOSE
   ============================================ */
document.addEventListener("click", (e) => {
  if (!sidebarUserBtn.contains(e.target) && !sidebarUserMenu.contains(e.target)) {
    sidebarUserMenu.hidden = true;
  }
  if (!documentsToggle.contains(e.target) && !documentsPanel.contains(e.target)) {
    documentsPanel.hidden = true;
  }
});

documentsToggle.addEventListener("click", (e) => {
  e.stopPropagation();
  documentsPanel.hidden = !documentsPanel.hidden;
});

/* ============================================
   USER AREA
   ============================================ */
async function initUserArea() {
  if (TOKEN) {
    try {
      const res = await fetch(API_BASE + "/auth/me", { headers: authHeaders() });
      const data = await res.json();
      sidebarUserName.textContent = data.email;
      sidebarUserAvatar.textContent = data.email[0].toUpperCase();
    } catch {
      sidebarUserName.textContent = "Account";
      sidebarUserAvatar.textContent = "?";
    }
    sidebarUserMenu.innerHTML = `<button type="button" class="sidebar-user-menu-item" id="logout-btn">Log out</button>`;
  } else {
    sidebarUserName.textContent = "Guest";
    sidebarUserAvatar.textContent = "G";
    sidebarUserMenu.innerHTML = `<a href="login.html" class="sidebar-user-menu-item">Log in</a>`;
  }

  sidebarUserBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    sidebarUserMenu.hidden = !sidebarUserMenu.hidden;
  });

  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("docquery_token");
      localStorage.removeItem("docquery_chat_session_id");
      localStorage.removeItem("docquery_guest_mode");
      window.location.href = "index.html";
    });
  }
}

/* ============================================
   SIDEBAR CHAT LIST
   ============================================ */
async function loadChatList() {
  if (!TOKEN) {
    sidebarChatList.innerHTML = `<li class="sidebar-chat-hint">Log in to save and revisit chats.</li>`;
    return;
  }

  const res = await fetch(API_BASE + "/chats", { headers: authHeaders() });
  if (!res.ok) return;
  const list = await res.json();

  sidebarChatList.innerHTML = "";
  list.forEach((c) => {
    const li = document.createElement("li");
    li.className = "sidebar-chat-item";
    if (c.id === CHAT_SESSION_ID) li.classList.add("is-active");

    const titleSpan = document.createElement("span");
    titleSpan.className = "sidebar-chat-title";
    titleSpan.textContent = c.title || "New chat";
    titleSpan.addEventListener("click", () => openChat(c.id));

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "sidebar-chat-delete";
    deleteBtn.setAttribute("aria-label", "Delete chat");
    deleteBtn.innerHTML = "&times;";
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      chatBeingDeleted = c.id;
      deleteOverlay.hidden = false;
    });

    li.appendChild(titleSpan);
    li.appendChild(deleteBtn);
    sidebarChatList.appendChild(li);
  });
}

deleteCancelBtn.addEventListener("click", () => {
  chatBeingDeleted = null;
  deleteOverlay.hidden = true;
});

deleteConfirmBtn.addEventListener("click", async () => {
  if (!chatBeingDeleted) return;
  const deletingCurrentChat = chatBeingDeleted === CHAT_SESSION_ID;

  try {
    await fetch(API_BASE + `/chats/${chatBeingDeleted}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
  } catch (err) {
    console.error(err);
  }

  deleteOverlay.hidden = true;
  chatBeingDeleted = null;

  if (deletingCurrentChat) {
    resetChatUI();
  }
  await loadChatList();
});

/* ============================================
   INIT
   ============================================ */
function init() {
  resetChatUI();
  initUserArea();
  loadChatList();

  if (CHAT_SESSION_ID) {
    openChat(CHAT_SESSION_ID);
  }
}

async function openChat(chatId) {
  CHAT_SESSION_ID = chatId;
  localStorage.setItem("docquery_chat_session_id", chatId);

  resetChatUI(false);

  const res = await fetch(API_BASE + `/chats/${chatId}`, { headers: authHeaders() });
  if (!res.ok) {
    await loadChatList();
    return;
  }

  const data = await res.json();
  state.documentReady = data.has_documents;
  currentChatTitle.textContent = data.title || "New chat";

  if (data.has_documents) {
    dropzoneText.textContent = "Tap to add another PDF to this chat";
    showUploadStatus("This chat already has document(s) — ask away, or add more.", false);
    enableChat();
  }

  renderDocumentsList(data.documents || []);

  data.messages.forEach((m) => {
    const el = appendMessage(m.role === "user" ? "user" : "assistant", m.content);
    if (m.sources && m.sources.length) renderSourceChips(el, m.sources);
  });

  await loadChatList();
}

function resetChatUI(clearSessionId = true) {
  if (clearSessionId) {
    CHAT_SESSION_ID = null;
    localStorage.removeItem("docquery_chat_session_id");
  }
  chatLog.innerHTML = "";
  chatEmpty.hidden = false;
  chatLog.appendChild(chatEmpty);
  state.documentReady = false;
  chatInput.disabled = true;
  chatSend.disabled = true;
  chatStatus.textContent = "Waiting for a document";
  chatStatus.classList.remove("is-ready");
  dropzoneText.textContent = "Tap to choose a PDF, or drag one in";
  dropzoneFilename.textContent = "";
  showUploadStatus("", false);
  renderDocumentsList([]);
  currentChatTitle.textContent = "New chat";
}

newChatBtn.addEventListener("click", () => {
  documentsPanel.hidden = true;
  resetChatUI();
  loadChatList();
});

function renderDocumentsList(filenames) {
  documentsList.innerHTML = "";
  if (filenames.length === 0) {
    documentsList.innerHTML = `<li class="documents-empty">No documents uploaded yet.</li>`;
    return;
  }
  filenames.forEach((name) => {
    const li = document.createElement("li");
    li.textContent = name;
    li.classList.add("documents-list-item");
    li.addEventListener("click", () => openDocumentPreview(name));
    documentsList.appendChild(li);
  });
}

async function ensureChatSession() {
  if (CHAT_SESSION_ID) return CHAT_SESSION_ID;

  const endpoint = TOKEN ? "/chats" : "/auth/guest";
  const res = await fetch(API_BASE + endpoint, { method: "POST", headers: authHeaders() });
  if (!res.ok) throw new Error("Couldn't start a new chat.");
  const data = await res.json();

  CHAT_SESSION_ID = data.chat_session_id;
  localStorage.setItem("docquery_chat_session_id", CHAT_SESSION_ID);
  return CHAT_SESSION_ID;
}

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

  try {
    const chatSessionId = await ensureChatSession();

    const formData = new FormData();
    formData.append("file", file);
    formData.append("chat_session_id", chatSessionId);

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

    const currentDocs = Array.from(documentsList.children)
      .filter((li) => !li.classList.contains("documents-empty"))
      .map((li) => li.textContent);
    renderDocumentsList([...currentDocs, file.name]);

    if (currentChatTitle.textContent === "New chat") {
      currentChatTitle.textContent = file.name;
    }

    await loadChatList();
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
}

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
    body: JSON.stringify({ chat_session_id: CHAT_SESSION_ID, question: message }),
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

init();