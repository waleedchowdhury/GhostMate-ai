const resultOutput = document.querySelector("#resultOutput");
const statusPill = document.querySelector("#statusPill");
const modelBadge = document.querySelector("#modelBadge");
const toolTitle = document.querySelector("#toolTitle");
const toolSubtitle = document.querySelector("#toolSubtitle");
const currentToolPill = document.querySelector("#currentToolPill");
const chatCommand = document.querySelector("#chatCommand");
const appWrapper = document.querySelector("#appWrapper");
const menuToggle = document.querySelector("#menuToggle");
const closeSidebar = document.querySelector("#closeSidebar");
const sidebarBackdrop = document.querySelector("#sidebarBackdrop");
const API_BASE = resolveApiBase();

let healthState = null;
let activeDocumentId = "";
let activeConversationId = "";
let activePanel = "emailPanel";

const toolLabels = {
  emailPanel: {
    pill: "Email mode",
    placeholder: "Ask GhostMate to draft, rewrite, improve, or personalize an email...",
  },
  pdfPanel: {
    pill: "PDF mode",
    placeholder: "Ask about the memorized PDF, study notes, summaries, questions, or explanations...",
  },
  assistantPanel: {
    pill: "Assistant mode",
    placeholder: "Ask GhostMate to plan, reason, research, or build a business workflow...",
  },
};

function updateAppHeight() {
  const viewport = window.visualViewport;
  const viewportHeight = viewport?.height || window.innerHeight;
  const viewportOffset = viewport?.offsetTop || 0;
  const keyboardInset = viewport
    ? Math.max(0, window.innerHeight - viewportHeight - viewportOffset)
    : 0;
  document.documentElement.style.setProperty("--app-height", `${Math.round(viewportHeight)}px`);
  document.documentElement.style.setProperty("--keyboard-inset", `${Math.round(keyboardInset)}px`);
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 980px)").matches;
}

function setSidebarOpen(isOpen) {
  if (isMobileLayout()) {
    appWrapper.classList.toggle("sidebar-open", isOpen);
    appWrapper.classList.remove("sidebar-collapsed");
  } else {
    appWrapper.classList.toggle("sidebar-collapsed", !isOpen);
    appWrapper.classList.remove("sidebar-open");
  }

  if (menuToggle) {
    menuToggle.setAttribute("aria-expanded", String(isOpen));
    menuToggle.textContent = isOpen && isMobileLayout() ? "Hide Tools" : "Tools";
  }
}

function toggleSidebar() {
  if (isMobileLayout()) {
    setSidebarOpen(!appWrapper.classList.contains("sidebar-open"));
  } else {
    setSidebarOpen(appWrapper.classList.contains("sidebar-collapsed"));
  }
}

function resolveApiBase() {
  const configuredBase = (window.GHOSTMATE_API_BASE || "").trim().replace(/\/$/, "");
  if (configuredBase) {
    return configuredBase;
  }

  if (window.location.protocol === "file:") {
    return "http://127.0.0.1:8000";
  }

  const host = window.location.hostname;
  if (host === "127.0.0.1" || host === "localhost") {
    return "";
  }

  return "";
}

function backendHelpMessage() {
  if (API_BASE) {
    return `Backend is not reachable at ${API_BASE}. Deploy or wake up the FastAPI server, then refresh GhostMate.`;
  }
  return "Backend is not connected. GitHub Pages only hosts the frontend, so the FastAPI backend must be deployed separately.";
}

async function request(url, options = {}) {
  try {
    return await fetch(`${API_BASE}${url}`, options);
  } catch (error) {
    throw new Error(backendHelpMessage());
  }
}

function setLoading(message) {
  addChatMessage("system", message);
}

function showResult(text) {
  addChatMessage("assistant", text || "No response returned.");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function isTableSeparator(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function renderTable(lines) {
  const rows = lines
    .filter((line) => !isTableSeparator(line))
    .map((line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim()));
  if (!rows.length) {
    return "";
  }

  const headers = rows[0];
  const bodyRows = rows.slice(1);
  const headerHtml = headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("");
  const bodyHtml = bodyRows
    .map((row) => `<tr>${row.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
}

function renderMarkdown(text) {
  const lines = text.trim().split(/\r?\n/);
  const html = [];
  let listType = "";
  let tableLines = [];

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = "";
    }
  };

  const flushTable = () => {
    if (tableLines.length) {
      closeList();
      html.push(renderTable(tableLines));
      tableLines = [];
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();

    if (trimmed.includes("|") && /^\|?.+\|.+/.test(trimmed)) {
      tableLines.push(trimmed);
      return;
    }

    flushTable();

    if (!trimmed) {
      closeList();
      return;
    }

    const heading = trimmed.match(/^#{1,4}\s+(.+)$/);
    if (heading) {
      closeList();
      html.push(`<h4>${renderInlineMarkdown(heading[1])}</h4>`);
      return;
    }

    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      if (listType !== "ul") {
        closeList();
        listType = "ul";
        html.push("<ul>");
      }
      html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      return;
    }

    const numbered = trimmed.match(/^\d+\.\s+(.+)$/);
    if (numbered) {
      if (listType !== "ol") {
        closeList();
        listType = "ol";
        html.push("<ol>");
      }
      html.push(`<li>${renderInlineMarkdown(numbered[1])}</li>`);
      return;
    }

    closeList();
    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  });

  flushTable();
  closeList();
  return html.join("");
}

function setMessageContent(bubble, role, text) {
  bubble.dataset.rawContent = text;
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(text);
  } else {
    bubble.textContent = text;
  }
}

async function postJson(url, data) {
  const response = await request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || backendHelpMessage());
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
  setMessageContent(bubble, role, text);
  resultOutput.appendChild(bubble);
  resultOutput.scrollTop = resultOutput.scrollHeight;
  return bubble;
}

function keepComposerVisible() {
  if (!isMobileLayout()) {
    return;
  }

  updateAppHeight();
  requestAnimationFrame(() => {
    resultOutput.scrollTop = resultOutput.scrollHeight;
    chatCommand.scrollIntoView({ block: "nearest", inline: "nearest" });
  });
}

function resizeComposer() {
  chatCommand.style.height = "auto";
  const maxHeight = isMobileLayout() ? 82 : 110;
  const nextHeight = Math.min(chatCommand.scrollHeight, maxHeight);
  chatCommand.style.height = `${nextHeight}px`;
  keepComposerVisible();
}

function activatePanel(panelId, options = {}) {
  const nextTab = document.querySelector(`.tab[data-panel="${panelId}"]`);
  const nextPanel = document.querySelector(`#${panelId}`);
  if (!nextTab || !nextPanel) {
    return;
  }

  document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));

  nextTab.classList.add("active");
  nextPanel.classList.add("active");
  activePanel = panelId;

  if (toolTitle) {
    toolTitle.textContent = nextTab.dataset.title || nextTab.textContent.trim();
  }
  if (toolSubtitle) {
    toolSubtitle.textContent = nextTab.dataset.subtitle || "";
  }
  if (currentToolPill) {
    currentToolPill.textContent = toolLabels[panelId]?.pill || "Agent mode";
  }
  if (chatCommand) {
    chatCommand.placeholder = toolLabels[panelId]?.placeholder || "Message GhostMate...";
  }

  if (options.announce) {
    addChatMessage("system", `Switched to ${toolLabels[panelId]?.pill || "agent mode"}.`);
  }

  if (isMobileLayout()) {
    setSidebarOpen(false);
  }
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

  const response = await request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || backendHelpMessage());
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
      const nextContent = `${assistantBubble.dataset.rawContent || ""}${chunk}`;
      setMessageContent(assistantBubble, "assistant", nextContent);
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
    activatePanel(tab.dataset.panel, { announce: true });
  });
});

menuToggle.addEventListener("click", toggleSidebar);
closeSidebar.addEventListener("click", () => setSidebarOpen(false));
sidebarBackdrop.addEventListener("click", () => setSidebarOpen(false));

window.addEventListener("resize", () => {
  updateAppHeight();
  setSidebarOpen(!isMobileLayout());
});

function handleViewportChange() {
  updateAppHeight();
  if (appWrapper.classList.contains("keyboard-open")) {
    keepComposerVisible();
  }
}

window.visualViewport?.addEventListener("resize", handleViewportChange);
window.visualViewport?.addEventListener("scroll", handleViewportChange);

chatCommand.addEventListener("focus", () => {
  if (isMobileLayout()) {
    appWrapper.classList.add("keyboard-open");
    updateAppHeight();
    setTimeout(keepComposerVisible, 80);
    setTimeout(keepComposerVisible, 260);
  }
});

chatCommand.addEventListener("blur", () => {
  appWrapper.classList.remove("keyboard-open");
  updateAppHeight();
});

document.querySelectorAll(".command-chip").forEach((button) => {
  button.addEventListener("click", () => {
    activatePanel(button.dataset.panel, { announce: false });
    chatCommand.value = button.dataset.message || "";
    resizeComposer();
    chatCommand.focus();
  });
});

document.querySelector("#pdfFile").addEventListener("change", () => {
  const file = document.querySelector("#pdfFile").files[0];
  if (file) {
    document.querySelector("#pdfMemoryStatus").textContent = `Ready to analyze: ${file.name}`;
    addChatMessage("system", `PDF selected: ${file.name}. Click Memorize PDF to start interactive PDF chat.`);
  }
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
    const response = await request("/api/pdf-summary", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || backendHelpMessage());
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

    const response = await request("/api/pdf-memory", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || backendHelpMessage());
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
    resizeComposer();
  });
});

document.querySelector("#chatCommand").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.querySelector("#sendCommand").click();
  }
});

document.querySelector("#chatCommand").addEventListener("input", resizeComposer);

async function checkBackend() {
  statusPill.textContent = "Backend online";
  statusPill.classList.add("ok");
  modelBadge.textContent = "Checking model...";

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await request("/health", {
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
    statusPill.textContent = "Backend offline";
    modelBadge.textContent = backendHelpMessage();
    statusPill.classList.add("warn");
  } finally {
    clearTimeout(timeout);
  }
}

updateAppHeight();
resizeComposer();
activatePanel(activePanel, { announce: false });
setSidebarOpen(!isMobileLayout());
checkBackend();
