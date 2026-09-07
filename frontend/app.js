const API_URL = "http://localhost:8000/chat";

const chatWindow = document.getElementById("chat-window");
const emptyState = document.getElementById("empty-state");
const form = document.getElementById("chat-form");
const input = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addUserMessage(text) {
  emptyState.style.display = "none";
  const wrapper = document.createElement("div");
  wrapper.className = "message user";
  wrapper.innerHTML = `<div class="bubble"></div>`;
  wrapper.querySelector(".bubble").textContent = text;
  chatWindow.appendChild(wrapper);
  scrollToBottom();
}

// Creates an empty bot message bubble and returns handles to update it
// as tokens stream in.
function addBotMessagePlaceholder() {
  const wrapper = document.createElement("div");
  wrapper.className = "message bot";
  wrapper.innerHTML = `<div class="bubble typing-cursor"></div>`;
  chatWindow.appendChild(wrapper);
  scrollToBottom();
  return {
    wrapper,
    bubble: wrapper.querySelector(".bubble"),
  };
}

function renderSources(wrapper, sources) {
  if (!sources || sources.length === 0) return;
  const sourcesEl = document.createElement("div");
  sourcesEl.className = "sources";

  sources.forEach((s) => {
    const item = document.createElement("div");
    item.className = "source-item";

    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "source-chip";
    chip.textContent = `${s.source} — page ${s.page}`;

    const preview = document.createElement("div");
    preview.className = "source-preview";
    preview.textContent = s.text || "";
    preview.hidden = true;

    chip.addEventListener("click", () => {
      preview.hidden = !preview.hidden;
      chip.classList.toggle("expanded", !preview.hidden);
    });

    item.appendChild(chip);
    item.appendChild(preview);
    sourcesEl.appendChild(item);
  });

  wrapper.appendChild(sourcesEl);
}

/**
 * Parses one SSE block of the form:
 *   event: token
 *   data: {"content":"..."}
 * into { event, data }.
 */
function parseSseBlock(block) {
  let event = "message";
  let dataLine = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLine += line.slice("data:".length).trim();
    }
  }
  let data = {};
  try {
    data = JSON.parse(dataLine || "{}");
  } catch (e) {
    // Ignore malformed data lines rather than crashing the stream reader.
  }
  return { event, data };
}

async function streamAnswer(question) {
  const { wrapper, bubble } = addBotMessagePlaceholder();
  sendBtn.disabled = true;

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Server responded with status ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let answerText = "";

    while (true) {
      const { value, done: streamDone } = await reader.read();
      if (streamDone) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line ("\n\n").
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (!block.trim()) continue;

        const { event, data } = parseSseBlock(block);

        if (event === "token") {
          answerText += data.content ?? "";
          bubble.textContent = answerText;
          scrollToBottom();
        } else if (event === "done") {
          bubble.classList.remove("typing-cursor");
        } else if (event === "sources") {
          renderSources(wrapper, data.sources);
          scrollToBottom();
        } else if (event === "error") {
          bubble.classList.remove("typing-cursor");
          bubble.classList.add("error");
          bubble.textContent = `Something went wrong: ${data.message || "unknown error"}`;
        }
      }
    }
  } catch (err) {
    bubble.classList.remove("typing-cursor");
    bubble.classList.add("error");
    bubble.textContent = `Something went wrong: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  addUserMessage(question);
  input.value = "";
  streamAnswer(question);
});