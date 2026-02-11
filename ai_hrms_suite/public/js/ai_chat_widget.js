/**
 * AI HRMS Chat Widget
 *
 * Floating chatbot available on every desk page.
 * Calls the 3-node hybrid pipeline:
 *   Intent (cheap) → Tools (free) → Response (smart, if needed)
 *
 * Session persisted in localStorage per user.
 */

(function () {
  "use strict";

  // ─── SVG icons ──────────────────────────────────────────────────────────────
  const ICON_CHAT =
    '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>';
  const ICON_SEND =
    '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  const ICON_CLOSE =
    '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/></svg>';
  const ICON_NEW =
    '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>';

  // ─── State ──────────────────────────────────────────────────────────────────
  const STORAGE_KEY = "ai_hrms_chat_session";
  let sessionId = null;
  let panelOpen = false;
  let sending = false;

  // ─── DOM refs ───────────────────────────────────────────────────────────────
  let $btn, $panel, $messages, $input, $sendBtn, $typingIndicator;

  // ─── Init ───────────────────────────────────────────────────────────────────
  function init() {
    // Only on desk (not login, setup wizard, etc.)
    if (!frappe.boot || !frappe.session || frappe.session.user === "Guest") return;

    sessionId = localStorage.getItem(STORAGE_KEY) || null;
    createDOM();
    bindEvents();
  }

  // ─── Build DOM ──────────────────────────────────────────────────────────────
  function createDOM() {
    // Floating button
    $btn = document.createElement("button");
    $btn.className = "ai-chat-btn";
    $btn.title = "AI HRMS Assistant";
    $btn.innerHTML = ICON_CHAT;
    document.body.appendChild($btn);

    // Panel
    $panel = document.createElement("div");
    $panel.className = "ai-chat-panel hidden";
    $panel.innerHTML = `
      <div class="ai-chat-header">
        <span class="ai-chat-header-title">AI HRMS Assistant</span>
        <span class="ai-chat-header-badge">AI</span>
        <div class="ai-chat-header-actions">
          <button class="ai-chat-new-btn" title="New conversation">${ICON_NEW}</button>
          <button class="ai-chat-close-btn" title="Close">${ICON_CLOSE}</button>
        </div>
      </div>
      <div class="ai-chat-messages"></div>
      <div class="ai-chat-input-area">
        <textarea class="ai-chat-input" placeholder="Ask anything about HRMS…" rows="1"></textarea>
        <button class="ai-chat-send-btn" disabled>${ICON_SEND}</button>
      </div>
    `;
    document.body.appendChild($panel);

    $messages = $panel.querySelector(".ai-chat-messages");
    $input = $panel.querySelector(".ai-chat-input");
    $sendBtn = $panel.querySelector(".ai-chat-send-btn");
  }

  // ─── Events ─────────────────────────────────────────────────────────────────
  function bindEvents() {
    $btn.addEventListener("click", togglePanel);

    $panel.querySelector(".ai-chat-close-btn").addEventListener("click", closePanel);
    $panel.querySelector(".ai-chat-new-btn").addEventListener("click", newSession);

    $sendBtn.addEventListener("click", sendMessage);

    $input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    $input.addEventListener("input", function () {
      // Auto-grow textarea
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 80) + "px";
      $sendBtn.disabled = !this.value.trim() || sending;
    });
  }

  // ─── Panel toggle ──────────────────────────────────────────────────────────
  function togglePanel() {
    panelOpen ? closePanel() : openPanel();
  }

  function openPanel() {
    $panel.classList.remove("hidden");
    panelOpen = true;

    // Show welcome if no messages yet
    if ($messages.children.length === 0) {
      showWelcome();
    }

    // Load history if we have a session but no messages rendered
    if (sessionId && $messages.querySelectorAll(".ai-chat-msg").length === 0) {
      loadHistory();
    }

    setTimeout(function () {
      $input.focus();
    }, 100);
  }

  function closePanel() {
    $panel.classList.add("hidden");
    panelOpen = false;
  }

  // ─── Welcome ────────────────────────────────────────────────────────────────
  function showWelcome() {
    $messages.innerHTML = `
      <div class="ai-chat-welcome">
        <div class="ai-chat-welcome-icon">🤖</div>
        <h4>AI HRMS Assistant</h4>
        <p>Ask me anything about employees, leaves, payroll, recruitment, attendance, and more.</p>
        <div class="ai-chat-suggestions">
          <span class="ai-chat-suggestion-chip" data-q="How do I apply for leave?">How do I apply for leave?</span>
          <span class="ai-chat-suggestion-chip" data-q="Show me pending leave applications">Pending leave applications</span>
          <span class="ai-chat-suggestion-chip" data-q="How does payroll processing work?">How does payroll work?</span>
        </div>
      </div>
    `;

    // Bind suggestion chips
    $messages.querySelectorAll(".ai-chat-suggestion-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        $input.value = this.getAttribute("data-q");
        $input.dispatchEvent(new Event("input"));
        sendMessage();
      });
    });
  }

  // ─── New session ────────────────────────────────────────────────────────────
  function newSession() {
    sessionId = null;
    localStorage.removeItem(STORAGE_KEY);
    $messages.innerHTML = "";
    showWelcome();
    $input.value = "";
    $input.style.height = "auto";
    $sendBtn.disabled = true;
  }

  // ─── Load history ───────────────────────────────────────────────────────────
  function loadHistory() {
    if (!sessionId) return;

    frappe.call({
      method: "ai_hrms_suite.api.chatbot.get_messages",
      args: { session_id: sessionId, limit: 30 },
      async: true,
      callback: function (r) {
        if (!r || !r.message || !r.message.messages) return;
        var msgs = r.message.messages;
        if (!msgs.length) return;

        // Clear welcome
        $messages.innerHTML = "";

        msgs.forEach(function (m) {
          if (m.role === "user") {
            appendBubble(m.content, "user");
          } else if (m.role === "assistant") {
            appendAssistantMessage(m.content, {
              sources_json: m.sources_json,
              confidence: null,
              latency_ms: m.latency_ms,
            });
          }
        });
        scrollToBottom();
      },
      error: function () {
        // Session might be invalid — reset
        sessionId = null;
        localStorage.removeItem(STORAGE_KEY);
      },
    });
  }

  // ─── Send message ──────────────────────────────────────────────────────────
  function sendMessage() {
    var text = ($input.value || "").trim();
    if (!text || sending) return;

    sending = true;
    $sendBtn.disabled = true;
    $input.value = "";
    $input.style.height = "auto";

    // Clear welcome if present
    var welcome = $messages.querySelector(".ai-chat-welcome");
    if (welcome) welcome.remove();

    // Show user bubble
    appendBubble(text, "user");

    // Show typing indicator
    showTyping();
    scrollToBottom();

    frappe.call({
      method: "ai_hrms_suite.api.chatbot.ask",
      args: { question: text, session_id: sessionId },
      async: true,
      callback: function (r) {
        hideTyping();
        sending = false;
        $sendBtn.disabled = !$input.value.trim();

        if (!r || !r.message) {
          appendBubble("Something went wrong. Please try again.", "error");
          scrollToBottom();
          return;
        }

        var data = r.message;

        // Persist session
        if (data.session_id) {
          sessionId = data.session_id;
          localStorage.setItem(STORAGE_KEY, sessionId);
        }

        // Show assistant response
        appendAssistantMessage(data.answer, {
          sources: data.sources,
          suggested_questions: data.suggested_questions,
          confidence: data.confidence,
          latency_ms: data.latency_ms,
          short_circuited: data.short_circuited,
        });
        scrollToBottom();
      },
      error: function (err) {
        hideTyping();
        sending = false;
        $sendBtn.disabled = !$input.value.trim();
        var errMsg = (err && err.message) || "Request failed. Please try again.";
        appendBubble(errMsg, "error");
        scrollToBottom();
      },
    });
  }

  // ─── Bubble rendering ──────────────────────────────────────────────────────
  function appendBubble(text, role) {
    var el = document.createElement("div");
    el.className = "ai-chat-msg ai-chat-msg-" + role;
    el.textContent = text;
    $messages.appendChild(el);
    return el;
  }

  function appendAssistantMessage(answer, opts) {
    opts = opts || {};

    // Main answer bubble
    var wrapper = document.createElement("div");
    wrapper.style.cssText = "align-self:flex-start;max-width:85%;";

    var bubble = document.createElement("div");
    bubble.className = "ai-chat-msg ai-chat-msg-assistant";
    bubble.textContent = answer || "(No response)";
    wrapper.appendChild(bubble);

    // Meta line (confidence + latency)
    if (opts.confidence || opts.latency_ms) {
      var meta = document.createElement("div");
      meta.className = "ai-chat-meta";
      var html = "";
      if (opts.confidence) {
        html +=
          '<span class="ai-chat-meta-dot ' +
          opts.confidence +
          '"></span> ' +
          opts.confidence;
      }
      if (opts.latency_ms) {
        html += (html ? " · " : "") + opts.latency_ms + "ms";
      }
      if (opts.short_circuited) {
        html += (html ? " · " : "") + "⚡ fast";
      }
      meta.innerHTML = html;
      wrapper.appendChild(meta);
    }

    // Suggested questions
    var suggestions = opts.suggested_questions || [];
    if (suggestions.length) {
      var container = document.createElement("div");
      container.className = "ai-chat-suggestions";
      suggestions.forEach(function (q) {
        var chip = document.createElement("span");
        chip.className = "ai-chat-suggestion-chip";
        chip.textContent = q;
        chip.setAttribute("data-q", q);
        chip.addEventListener("click", function () {
          $input.value = this.getAttribute("data-q");
          $input.dispatchEvent(new Event("input"));
          sendMessage();
        });
        container.appendChild(chip);
      });
      wrapper.appendChild(container);
    }

    $messages.appendChild(wrapper);
  }

  // ─── Typing indicator ──────────────────────────────────────────────────────
  function showTyping() {
    if ($typingIndicator) return;
    $typingIndicator = document.createElement("div");
    $typingIndicator.className = "ai-chat-typing";
    $typingIndicator.innerHTML =
      '<span class="ai-chat-typing-dot"></span>' +
      '<span class="ai-chat-typing-dot"></span>' +
      '<span class="ai-chat-typing-dot"></span>';
    $messages.appendChild($typingIndicator);
  }

  function hideTyping() {
    if ($typingIndicator) {
      $typingIndicator.remove();
      $typingIndicator = null;
    }
  }

  // ─── Scroll ─────────────────────────────────────────────────────────────────
  function scrollToBottom() {
    setTimeout(function () {
      $messages.scrollTop = $messages.scrollHeight;
    }, 50);
  }

  // ─── Boot ───────────────────────────────────────────────────────────────────
  // Wait for Frappe desk to be ready
  if (typeof frappe !== "undefined" && frappe.ready) {
    frappe.ready(function () {
      init();
    });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      // Retry after frappe is available
      var interval = setInterval(function () {
        if (typeof frappe !== "undefined" && frappe.boot) {
          clearInterval(interval);
          init();
        }
      }, 500);
    });
  }
})();
