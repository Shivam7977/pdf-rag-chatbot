/* ============================================
   CONFIG
   Adjust these to match your actual FastAPI routes
   (app/api/documents.py and app/api/chat.py).
   ============================================ */
const CONFIG = {
  UPLOAD_ENDPOINT: "/api/documents/upload", // matches app/api/documents.py
  CHAT_ENDPOINT: "/chat",                   // matches app/api/chat.py's @router.post("/chat")
};

/* ============================================
   STATE
   ============================================ */
const state = {
  // Every filename uploaded in THIS session (page load). Sent to the backend
  // with each chat request so retrieval only searches these documents —
  // not every PDF ever uploaded to the app.
  uploadedSources: [],
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
const topicsBlock = document.getElementById("topics-block");
const topicChips = document.getElementById("topic-chips");

const chatStatus = document.getElementById("chat-status");
const chatLog = document.getElementById("chat-log");
const chatEmpty = document.getElementById("chat-empty");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");

/* ============================================
   UPLOAD
   ============================================ */
dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("is-dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("is-dragover");
});

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
  hideElement(topicsBlock);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(CONFIG.UPLOAD_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error(`Upload failed (${res.status})`);
    }

    const data = await res.json();

    // Adjust this field name if your upload response shape differs.
    const uploadedFilename = data.filename ?? file.name;
    if (!state.uploadedSources.includes(uploadedFilename)) {
      state.uploadedSources.push(uploadedFilename);
    }
    state.documentReady = true;

    dropzoneText.textContent = "Tap to add another PDF to this chat";
    showUploadStatus(
      state.uploadedSources.length > 1
        ? `${state.uploadedSources.length} documents ready in this chat.`
        : `"${file.name}" is indexed and ready.`,
      false
    );

    if (Array.isArray(data.topics) && data.topics.length > 0) {
      renderTopics(data.topics);
    }

    enableChat();
  } catch (err) {
    console.error(err);
    dropzoneText.textContent = "Tap to choose a PDF, or drag one in";
    showUploadStatus(
      "Couldn't upload that file. Check that the backend is running and CONFIG.UPLOAD_ENDPOINT is correct.",
      true
    );
  }
}

function showUploadStatus(message, isError) {
  uploadStatus.textContent = message;
  uploadStatus.hidden = !message;
  uploadStatus.classList.toggle("is-error", isError);
}

function renderTopics(topics) {
  topicChips.innerHTML = "";
  topics.forEach((topic) => {
    const li = document.createElement("li");
    li.textContent = topic;
    topicChips.appendChild(li);
  });
  showElement(topicsBlock);
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
   (POST is required, so EventSource can't be used)
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
    setMessageText(assistantEl, "Something went wrong reaching the backend. Check CONFIG.CHAT_ENDPOINT.");
  } finally {
    stopStreamingCursor(assistantEl);
    chatInput.disabled = false;
    chatSend.disabled = false;
    chatInput.focus();
  }
});

async function streamAnswer(message, assistantEl) {
  // "sources" scopes retrieval to only the PDFs uploaded in this session —
  // see app/schemas/chat.py.
  const res = await fetch(CONFIG.CHAT_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: message,
      sources: state.uploadedSources,
    }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answerText = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line
    const parts = buffer.split("\n\n");
    buffer = parts.pop(); // keep the last, possibly incomplete, chunk

    for (const part of parts) {
      const { event, data } = parseSSEEvent(part);
      if (!event || data === null) continue;

      // Every event's data is a JSON object, per app/api/chat.py's sse_event():
      //   token   -> {"content": "..."}
      //   sources -> {"sources": [{page, source, text}, ...]}
      //   error   -> {"message": "..."}
      //   done    -> {}
      let payload;
      try {
        payload = JSON.parse(data);
      } catch {
        continue; // malformed event, skip it rather than crash the stream
      }

      if (event === "token") {
        answerText += payload.content ?? "";
        setMessageText(assistantEl, answerText, { streaming: true });
      } else if (event === "sources") {
        renderSourceChips(assistantEl, payload.sources ?? []);
      } else if (event === "error") {
        setMessageText(assistantEl, payload.message || "The assistant couldn't answer that.");
      } else if (event === "done") {
        // no-op — cursor removal happens in the caller's finally block
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
    const label = s.page ? `${s.source} · p.${s.page}` : s.source;
    chip.textContent = label;
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

function showElement(el) { el.hidden = false; }
function hideElement(el) { el.hidden = true; }