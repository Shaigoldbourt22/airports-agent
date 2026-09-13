const log = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const send = document.getElementById("send");
const welcome = document.getElementById("welcome");
const attachBtn = document.getElementById("attach");
const fileInput = document.getElementById("file");
const attachmentBar = document.getElementById("attachments");
const account = document.querySelector(".account");
const userEmail = document.getElementById("user-email");
const sidebar = document.getElementById("sidebar");
const sessionList = document.getElementById("session-list");
const newChatBtn = document.getElementById("new-chat");
const toggleSidebar = document.getElementById("toggle-sidebar");

let currentSessionId = null;

const WELCOME_HTML = welcome?.outerHTML;

function resetView() {
  log.textContent = "";
  if (WELCOME_HTML) {
    log.insertAdjacentHTML("beforeend", WELCOME_HTML);
    bindChips();
  }
}

function startNewChat() {
  currentSessionId = null;
  history.length = 0;
  pendingFiles.length = 0;
  renderAttachments();
  resetView();
  markActiveSession();
  input.focus();
}

function markActiveSession() {
  for (const el of sessionList.querySelectorAll(".session")) {
    el.classList.toggle("active", el.dataset.id === currentSessionId);
  }
}

async function loadSessions() {
  const res = await fetch("/api/sessions").catch(() => null);
  if (!res?.ok) return;
  const items = await res.json();
  sessionList.textContent = "";
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "session";
    row.dataset.id = item.id;

    const open = document.createElement("button");
    open.type = "button";
    open.className = "session-open";
    open.textContent = item.title;
    open.addEventListener("click", () => openSession(item.id));

    const del = document.createElement("button");
    del.type = "button";
    del.className = "session-delete";
    del.textContent = "\u00d7";
    del.setAttribute("aria-label", `Delete ${item.title}`);
    del.addEventListener("click", async () => {
      await fetch(`/api/sessions/${item.id}`, { method: "DELETE" });
      if (currentSessionId === item.id) startNewChat();
      loadSessions();
    });

    row.append(open, del);
    sessionList.appendChild(row);
  }
  markActiveSession();
}

async function openSession(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}`).catch(() => null);
  if (!res?.ok) return;
  const messages = await res.json();
  currentSessionId = sessionId;
  history.length = 0;
  log.textContent = "";
  for (const message of messages) {
    history.push({ role: message.role, content: message.content });
    addMessage(message.role, message.content, message.file_names);
  }
  markActiveSession();
}

newChatBtn.addEventListener("click", startNewChat);

toggleSidebar.addEventListener("click", () => {
  sidebar.hidden = !sidebar.hidden;
});

loadSessions();

fetch("/.auth/me")
  .then((res) => (res.ok ? res.json() : null))
  .then((data) => {
    const claims = data?.[0]?.user_claims || [];
    const email =
      data?.[0]?.user_id ||
      claims.find((c) => c.typ.endsWith("emailaddress") || c.typ === "email")?.val;
    if (!email) return;
    userEmail.textContent = email;
    account.hidden = false;
  })
  .catch(() => {});

const MAX_FILE_BYTES = 8 * 1024 * 1024;
const MAX_FILES = 5;

const history = [];
const pendingFiles = [];

function renderAttachments() {
  attachmentBar.textContent = "";
  attachmentBar.hidden = pendingFiles.length === 0;
  pendingFiles.forEach((file, index) => {
    const tag = document.createElement("span");
    tag.className = "file-tag";
    tag.textContent = file.name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "file-remove";
    remove.setAttribute("aria-label", `Remove ${file.name}`);
    remove.textContent = "\u00d7";
    remove.addEventListener("click", () => {
      pendingFiles.splice(index, 1);
      renderAttachments();
    });
    tag.appendChild(remove);
    attachmentBar.appendChild(tag);
  });
}

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.readAsDataURL(file);
  });
}

function addMessage(role, text, fileNames = []) {
  document.getElementById("welcome")?.remove();
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  if (text) el.textContent = text;
  if (fileNames.length) {
    const list = document.createElement("div");
    list.className = "msg-files";
    for (const name of fileNames) {
      const tag = document.createElement("span");
      tag.textContent = name;
      list.appendChild(tag);
    }
    el.appendChild(list);
  }
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function showTyping(el) {
  el.textContent = "";
  const dots = document.createElement("span");
  dots.className = "dots";
  dots.innerHTML = "<span></span><span></span><span></span>";
  el.appendChild(dots);
}

function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${input.scrollHeight}px`;
}

async function ask(text, attachments = []) {
  history.push({ role: "user", content: text, attachments });
  addMessage("user", text, attachments.map((a) => a.name));

  const pending = addMessage("assistant", "");
  showTyping(pending);
  send.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: history.slice(-20),
        session_id: currentSessionId,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    const data = await res.json();
    pending.textContent = data.reply;
    history.push({ role: "assistant", content: data.reply });
    currentSessionId = data.session_id;
    loadSessions();
  } catch (err) {
    pending.className = "msg error";
    pending.textContent = err.message;
    history.pop();
  } finally {
    send.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text && pendingFiles.length === 0) return;
  const attachments = pendingFiles.splice(0);
  renderAttachments();
  input.value = "";
  autoGrow();
  ask(text, attachments);
});

input.addEventListener("input", autoGrow);

attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  for (const file of fileInput.files) {
    if (pendingFiles.length >= MAX_FILES) {
      addMessage("error", `Up to ${MAX_FILES} files per message.`);
      break;
    }
    if (file.size > MAX_FILE_BYTES) {
      addMessage("error", `${file.name} is larger than 8 MB.`);
      continue;
    }
    try {
      pendingFiles.push({
        name: file.name,
        mime_type: file.type || "application/octet-stream",
        data: await readAsBase64(file),
      });
    } catch (err) {
      addMessage("error", err.message);
    }
  }
  fileInput.value = "";
  renderAttachments();
});

function bindChips() {
  for (const chip of document.querySelectorAll(".chip")) {
    chip.addEventListener("click", () => ask(chip.textContent.trim()));
  }
}

bindChips();

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

const mic = document.getElementById("mic");
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
  mic.disabled = true;
  mic.title = "Speech recognition is not supported in this browser";
} else {
  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  let listening = false;
  let baseText = "";

  recognition.addEventListener("start", () => {
    listening = true;
    baseText = input.value.trim();
    mic.classList.add("listening");
  });

  recognition.addEventListener("result", (event) => {
    let transcript = "";
    for (const result of event.results) transcript += result[0].transcript;
    input.value = (baseText ? `${baseText} ` : "") + transcript.trim();
  });

  recognition.addEventListener("error", (event) => {
    if (event.error !== "aborted" && event.error !== "no-speech") {
      addMessage("error", `Speech recognition failed: ${event.error}`);
    }
  });

  recognition.addEventListener("end", () => {
    listening = false;
    mic.classList.remove("listening");
    input.focus();
  });

  mic.addEventListener("click", () => {
    if (listening) recognition.stop();
    else recognition.start();
  });
}
