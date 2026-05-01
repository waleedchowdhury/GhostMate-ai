const resultOutput = document.querySelector("#resultOutput");
const statusPill = document.querySelector("#statusPill");
const modelBadge = document.querySelector("#modelBadge");
const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

let healthState = null;
let activeDocumentId = "";
let activeConversationId = "";
let activePanel = "emailPanel";

function setLoading(message) {
  addChatMessage("system", message);
}

function showResult(text) {
  addChatMessage("assistant", text || "No response returned.");
}

async function postJson(url, data) {
  const response = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Request failed.");
  }

  return response.json();
}

function requireValue(selector, message) {
  const element = document.querySelector(selector);
  const value = element.value.trim();
  if (!value) {
    element.focus();
    throw new Error(message);
  }
  return value;
}

async function withBusy(button, label, action) {
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = label;

  try {
    await action();
  } catch (error) {
    showResult(error.message);
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function startChatThread() {
  resultOutput.textContent = "";
  resultOutput.classList.add("chat-thread");
}

function addChatMessage(role, text = "") {
  if (!resultOutput.classList.contains("chat-thread")) {
    startChatThread();
  }

  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  resultOutput.appendChild(bubble);
  resultOutput.scrollTop = resultOutput.scrollHeight;
  return bubble;
}

function absorbConversationMarker(text) {
  const match = text.match(/\[conversation_id:([^\]]+)\]\n?/);
  if (match) {
    activeConversationId = match[1];
    return text.replace(match[0], "");
  }
  return text;
}

async function streamPost(url, data, options = {}) {
  let assistantBubble = null;
  if (options.chat) {
    if (!resultOutput.classList.contains("chat-thread")) {
      startChatThread();
    }
    addChatMessage("user", options.userMessage || data.message);
    assistantBubble = addChatMessage("assistant", "");
  } else {
    resultOutput.classList.add("chat-thread");
    resultOutput.textContent = "";
    assistantBubble = addChatMessage("assistant", "");
  }

  const response = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Streaming request failed.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    const chunk = absorbConversationMarker(decoder.decode(value, { stream: true }));
    if (assistantBubble) {
      assistantBubble.textContent += chunk;
    } else {
      resultOutput.textContent += chunk;
    }
    resultOutput.scrollTop = resultOutput.scrollHeight;
  }
}

function getPlainChatText() {
  return Array.from(resultOutput.querySelectorAll(".message"))
    .map((item) => item.textContent)
    .join("\n\n");
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));

    tab.classList.add("active");
    document.querySelector(`#${tab.dataset.panel}`).classList.add("active");
    activePanel = tab.dataset.panel;
  });
});

document.querySelector("#generateEmail").addEventListener("click", async () => {
  const button = document.querySelector("#generateEmail");

  await withBusy(button, "Writing...", async () => {
    const purpose = requireValue("#emailPurpose", "Please describe what the email should do.");
    addChatMessage("user", `Write email: ${purpose}`);
    const data = await postJson("/api/email", {
      purpose,
      recipient: document.querySelector("#emailRecipient").value.trim(),
      tone: document.querySelector("#emailTone").value,
      email_type: document.querySelector("#emailType").value,
      audience: document.querySelector("#emailAudience").value.trim(),
      offer: document.querySelector("#emailOffer").value.trim(),
      call_to_action: document.querySelector("#emailCta").value.trim(),
      details: document.querySelector("#emailDetails").value.trim(),
    });
    addChatMessage("assistant", data.result);
  });
});

document.querySelector("#summarizePdf").addEventListener("click", async () => {
  const button = document.querySelector("#summarizePdf");

  await withBusy(button, "Summarizing...", async () => {
    const file = document.querySelector("#pdfFile").files[0];
    if (!file) {
      throw new Error("Please choose a PDF file first.");
    }

    addChatMessage("user", "Generate a full study summary from the uploaded PDF.");
    addChatMessage("system", "Reading the PDF and building a multi-stage study summary. Large books can take several minutes...");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("summary_mode", document.querySelector("#pdfMode").value);
    formData.append("target_length", document.querySelector("#pdfLength").value);
    formData.append("detail_level", document.querySelector("#pdfDetail").value);
    formData.append("focus", document.querySelector("#pdfFocus").value.trim());
    const response = await fetch(`${API_BASE}/api/pdf-summary`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "PDF summary failed.");
    }

    const data = await response.json();
    addChatMessage("assistant", data.result);
  });
});

document.querySelector("#memorizePdf").addEventListener("click", async () => {
  const button = document.querySelector("#memorizePdf");

  await withBusy(button, "Memorizing...", async () => {
    const file = document.querySelector("#pdfFile").files[0];
    if (!file) {
      throw new Error("Please choose a PDF file first.");
    }

    addChatMessage("user", "Memorize this PDF for chat.");
    addChatMessage("system", "Reading and memorizing PDF for interactive chat...");
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE}/api/pdf-memory`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "PDF memory failed.");
    }

    const data = await response.json();
    activeDocumentId = data.document_id;
    activeConversationId = "";
    document.querySelector("#pdfMemoryStatus").textContent =
      `Memorized ${data.filename}: ${data.readable_pages} readable pages, ${data.chunks} memory chunks.`;
    addChatMessage("assistant", data.quick_summary);
  });
});

async function askPdf(message) {
  if (!activeDocumentId) {
    throw new Error("Please memorize a PDF first.");
  }

  await streamPost(
    "/api/chat/stream",
    {
      message,
      conversation_id: activeConversationId,
      document_id: activeDocumentId,
      mode: document.querySelector("#pdfMode").value,
    },
    { chat: true, userMessage: message },
  );
}

document.querySelectorAll(".quick-pdf").forEach((button) => {
  button.addEventListener("click", async () => {
    await withBusy(button, "Streaming...", async () => {
      const message = button.dataset.message;
      document.querySelector("#chatCommand").value = message;
      await askPdf(message);
    });
  });
});

document.querySelector("#askAssistant").addEventListener("click", async () => {
  const button = document.querySelector("#askAssistant");

  await withBusy(button, "Thinking...", async () => {
    const task = requireValue("#assistantTask", "Please enter a task for GhostMate.");
    addChatMessage("user", task);
    const data = await postJson("/api/assistant", {
      task,
      context: document.querySelector("#assistantContext").value.trim(),
      mode: document.querySelector("#assistantMode").value,
    });
    addChatMessage("assistant", data.result);
  });
});

document.querySelector("#copyResult").addEventListener("click", async () => {
  await navigator.clipboard.writeText(getPlainChatText());
});

document.querySelector("#clearChat").addEventListener("click", () => {
  activeConversationId = "";
  startChatThread();
  addChatMessage("assistant", "New chat started. Send a command or upload a PDF to continue.");
});

document.querySelector("#sendCommand").addEventListener("click", async () => {
  const button = document.querySelector("#sendCommand");
  await withBusy(button, "Sending...", async () => {
    const message = requireValue("#chatCommand", "Type a message for GhostMate.");
    if (activePanel === "pdfPanel") {
      await askPdf(message);
    } else {
      await streamPost(
        "/api/chat/stream",
        {
          message,
          conversation_id: activeConversationId,
          document_id: "",
          mode: activePanel === "assistantPanel" ? document.querySelector("#assistantMode").value : "business",
        },
        { chat: true, userMessage: message },
      );
    }
    document.querySelector("#chatCommand").value = "";
  });
});

document.querySelector("#chatCommand").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.querySelector("#sendCommand").click();
  }
});

async function checkBackend() {
  statusPill.textContent = "Backend online";
  statusPill.classList.add("ok");
  modelBadge.textContent = "Checking model...";

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1500);

  try {
    const response = await fetch(`${API_BASE}/health`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error("Backend not ready");
    }

    const data = await response.json();
    healthState = data;
    const ai = data.ai || {};
    statusPill.textContent = ai.configured ? "Ready" : "Local mode";
    modelBadge.textContent = ai.configured ? `Model: ${ai.model}` : "Mode: local fallback";
    statusPill.classList.toggle("warn", !ai.configured);
  } catch (error) {
    statusPill.textContent = "Backend slow";
    modelBadge.textContent = "Still usable if server is starting. Refresh in a moment.";
    statusPill.classList.add("warn");
  } finally {
    clearTimeout(timeout);
  }
}

checkBackend();
