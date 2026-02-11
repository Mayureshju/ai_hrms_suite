/**
 * AI HRMS Chat Widget
 *
 * Floating chatbot available on every desk page.
 * Calls the 3-node hybrid pipeline:
 *   Intent (cheap) → Tools (free) → Response (smart, if needed)
 *
 * Features:
 *   - Expandable panel with session sidebar (no page navigation)
 *   - Excel / CSV export for list-type answers
 *   - Session management: create, switch, delete, search
 */

(function () {
  "use strict";

  // ─── SVG Icons ─────────────────────────────────────────────────────────────
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  var ICON_CLOSE =
    '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/></svg>';
  var ICON_NEW =
    '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>';
  var ICON_EXPAND =
    '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" fill="currentColor"/></svg>';
  var ICON_COLLAPSE =
    '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" fill="currentColor"/></svg>';
  var ICON_DOWNLOAD =
    '<svg viewBox="0 0 24 24" width="14" height="14"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor"/></svg>';
  var ICON_DELETE =
    '<svg viewBox="0 0 24 24" width="14" height="14"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>';

  // ─── State ─────────────────────────────────────────────────────────────────
  var STORAGE_KEY = "ai_hrms_chat_session";
  var sessionId = null;
  var panelOpen = false;
  var sending = false;
  var expanded = false;
  var sessions = [];
  var sessionsLoaded = false;
  var lastExportInfo = null; // tracks last export_info for "download" requests

  // ─── DOM refs ──────────────────────────────────────────────────────────────
  var $btn, $panel, $messages, $input, $sendBtn, $typingIndicator;
  var $sessionList, $sessionSearch, $expandBtn;

  // ─── Init ──────────────────────────────────────────────────────────────────
  function init() {
    if (!frappe.boot || !frappe.session || frappe.session.user === "Guest") return;
    sessionId = localStorage.getItem(STORAGE_KEY) || null;
    createDOM();
    bindEvents();
  }

  // ─── Build DOM ─────────────────────────────────────────────────────────────
  function createDOM() {
    // Floating trigger button
    $btn = document.createElement("button");
    $btn.className = "ai-chat-btn";
    $btn.title = "AI HRMS Assistant";
    $btn.innerHTML = ICON_CHAT;
    document.body.appendChild($btn);

    // Panel
    $panel = document.createElement("div");
    $panel.className = "ai-chat-panel hidden";
    $panel.innerHTML =
      '<div class="ai-chat-header">' +
        '<span class="ai-chat-header-title">AI HRMS Assistant</span>' +
        '<span class="ai-chat-header-badge">AI</span>' +
        '<div class="ai-chat-header-actions">' +
          '<button class="ai-chat-expand-btn" title="Expand">' + ICON_EXPAND + '</button>' +
          '<button class="ai-chat-new-btn" title="New conversation">' + ICON_NEW + '</button>' +
          '<button class="ai-chat-close-btn" title="Close">' + ICON_CLOSE + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="ai-chat-body">' +
        '<div class="ai-chat-sidebar">' +
          '<div class="ai-chat-sidebar-header">' +
            '<span class="ai-chat-sidebar-title">Your chats</span>' +
          '</div>' +
          '<div class="ai-chat-sidebar-actions">' +
            '<button class="ai-chat-sidebar-new">+ New chat</button>' +
          '</div>' +
          '<div class="ai-chat-sidebar-search">' +
            '<input class="ai-chat-sidebar-search-input" placeholder="Search chats..." />' +
          '</div>' +
          '<div class="ai-chat-session-list"></div>' +
        '</div>' +
        '<div class="ai-chat-main">' +
          '<div class="ai-chat-messages"></div>' +
          '<div class="ai-chat-input-area">' +
            '<textarea class="ai-chat-input" placeholder="Ask anything about HRMS\u2026" rows="1"></textarea>' +
            '<button class="ai-chat-send-btn" disabled>' + ICON_SEND + '</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.body.appendChild($panel);

    $messages = $panel.querySelector(".ai-chat-messages");
    $input = $panel.querySelector(".ai-chat-input");
    $sendBtn = $panel.querySelector(".ai-chat-send-btn");
    $sessionList = $panel.querySelector(".ai-chat-session-list");
    $sessionSearch = $panel.querySelector(".ai-chat-sidebar-search-input");
    $expandBtn = $panel.querySelector(".ai-chat-expand-btn");
  }

  // ─── Events ────────────────────────────────────────────────────────────────
  function bindEvents() {
    $btn.addEventListener("click", togglePanel);
    $panel.querySelector(".ai-chat-close-btn").addEventListener("click", closePanel);
    $expandBtn.addEventListener("click", toggleExpand);
    $panel.querySelector(".ai-chat-new-btn").addEventListener("click", newSession);
    $panel.querySelector(".ai-chat-sidebar-new").addEventListener("click", function () {
      newSession();
      loadSessions();
    });

    $sendBtn.addEventListener("click", sendMessage);

    $input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    $input.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 80) + "px";
      $sendBtn.disabled = !this.value.trim() || sending;
    });

    if ($sessionSearch) {
      $sessionSearch.addEventListener("input", function () {
        filterSessions(this.value || "");
      });
    }
  }

  // ─── Panel toggle ─────────────────────────────────────────────────────────
  function togglePanel() {
    panelOpen ? closePanel() : openPanel();
  }

  function openPanel() {
    $panel.classList.remove("hidden");
    panelOpen = true;
    if ($messages.children.length === 0) showWelcome();
    if (sessionId && $messages.querySelectorAll(".ai-chat-msg").length === 0) loadHistory();
    setTimeout(function () { $input.focus(); }, 100);
  }

  function closePanel() {
    $panel.classList.add("hidden");
    panelOpen = false;
  }

  // ─── Expand / collapse (in-place, no route change) ────────────────────────
  function toggleExpand() {
    expanded = !expanded;
    if (expanded) {
      $panel.classList.add("expanded");
      $expandBtn.innerHTML = ICON_COLLAPSE;
      $expandBtn.title = "Collapse";
      if (!sessionsLoaded) loadSessions();
    } else {
      $panel.classList.remove("expanded");
      $expandBtn.innerHTML = ICON_EXPAND;
      $expandBtn.title = "Expand";
    }
  }

  // ─── Welcome ───────────────────────────────────────────────────────────────
  function showWelcome() {
    $messages.innerHTML =
      '<div class="ai-chat-welcome">' +
        '<div class="ai-chat-welcome-icon">\uD83E\uDD16</div>' +
        '<h4>AI HRMS Assistant</h4>' +
        '<p>Ask me anything about employees, leaves, payroll, recruitment, attendance, and more.</p>' +
        '<div class="ai-chat-suggestions">' +
          '<span class="ai-chat-suggestion-chip" data-q="How do I apply for leave?">How do I apply for leave?</span>' +
          '<span class="ai-chat-suggestion-chip" data-q="Show me pending leave applications">Pending leave applications</span>' +
          '<span class="ai-chat-suggestion-chip" data-q="How does payroll processing work?">How does payroll work?</span>' +
        '</div>' +
      '</div>';

    bindSuggestionChips($messages);
  }

  function bindSuggestionChips(container) {
    var chips = container.querySelectorAll(".ai-chat-suggestion-chip");
    for (var i = 0; i < chips.length; i++) {
      chips[i].addEventListener("click", function () {
        $input.value = this.getAttribute("data-q");
        $input.dispatchEvent(new Event("input"));
        sendMessage();
      });
    }
  }

  // ─── New session ───────────────────────────────────────────────────────────
  function newSession() {
    sessionId = null;
    lastExportInfo = null;
    localStorage.removeItem(STORAGE_KEY);
    $messages.innerHTML = "";
    showWelcome();
    $input.value = "";
    $input.style.height = "auto";
    $sendBtn.disabled = true;

    if (expanded && $sessionList) {
      var items = $sessionList.querySelectorAll(".ai-chat-session-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.remove("active");
      }
    }
  }

  // ─── Load history ──────────────────────────────────────────────────────────
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
        $messages.innerHTML = "";
        for (var i = 0; i < msgs.length; i++) {
          var m = msgs[i];
          if (m.role === "user") {
            appendBubble(m.content, "user");
          } else if (m.role === "assistant") {
            appendAssistantMessage(m.content, {
              sources_json: m.sources_json,
              confidence: null,
              latency_ms: m.latency_ms,
            });
          }
        }
        scrollToBottom();
      },
      error: function () {
        sessionId = null;
        localStorage.removeItem(STORAGE_KEY);
      },
    });
  }

  // ─── Sessions sidebar ─────────────────────────────────────────────────────
  function loadSessions() {
    if (!$sessionList) return;
    frappe.call({
      method: "ai_hrms_suite.api.chatbot.list_sessions",
      args: { limit: 50 },
      async: true,
      callback: function (r) {
        sessionsLoaded = true;
        sessions = (r && r.message && r.message.sessions) || [];
        renderSessionList();
      },
    });
  }

  function renderSessionList() {
    if (!$sessionList) return;
    $sessionList.innerHTML = "";

    if (!sessions || !sessions.length) {
      var empty = document.createElement("div");
      empty.className = "ai-chat-session-empty";
      empty.textContent = "No chats yet";
      $sessionList.appendChild(empty);
      return;
    }

    for (var i = 0; i < sessions.length; i++) {
      (function (s) {
        var item = document.createElement("div");
        item.className = "ai-chat-session-item";
        if (s.name === sessionId) item.classList.add("active");
        var title = s.title || "New Chat";
        var created = s.last_message_on || s.creation;

        item.innerHTML =
          '<div class="ai-chat-session-main">' +
            '<div class="ai-chat-session-title">' + frappe.utils.escape_html(title) + '</div>' +
            '<div class="ai-chat-session-time">' + frappe.datetime.prettyDate(created) + '</div>' +
          '</div>' +
          '<button class="ai-chat-session-delete" title="Delete">' + ICON_DELETE + '</button>';

        // Open session
        item.querySelector(".ai-chat-session-main").addEventListener("click", function () {
          sessionId = s.name;
          lastExportInfo = null;
          localStorage.setItem(STORAGE_KEY, sessionId);
          var allItems = $sessionList.querySelectorAll(".ai-chat-session-item");
          for (var j = 0; j < allItems.length; j++) {
            allItems[j].classList.toggle("active", allItems[j] === item);
          }
          $messages.innerHTML = "";
          loadHistory();
        });

        // Delete session
        item.querySelector(".ai-chat-session-delete").addEventListener("click", function (e) {
          e.stopPropagation();
          frappe.confirm("Delete this chat and all its messages?", function () {
            frappe.call({
              method: "ai_hrms_suite.api.chatbot.delete_session",
              args: { session_id: s.name },
              async: true,
              callback: function () {
                sessions = sessions.filter(function (x) { return x.name !== s.name; });
                if (sessionId === s.name) newSession();
                renderSessionList();
                frappe.show_alert({ message: "Chat deleted", indicator: "green" });
              },
            });
          });
        });

        $sessionList.appendChild(item);
      })(sessions[i]);
    }
  }

  function filterSessions(query) {
    if (!$sessionList) return;
    var q = (query || "").toLowerCase();
    var items = $sessionList.querySelectorAll(".ai-chat-session-item");
    for (var i = 0; i < items.length; i++) {
      var titleEl = items[i].querySelector(".ai-chat-session-title");
      var text = (titleEl && titleEl.textContent.toLowerCase()) || "";
      items[i].style.display = !q || text.indexOf(q) !== -1 ? "" : "none";
    }
  }

  // ─── Send message ──────────────────────────────────────────────────────────
  function sendMessage() {
    var text = ($input.value || "").trim();
    if (!text || sending) return;

    // Intercept direct export requests: "download excel", "export csv", etc.
    if (lastExportInfo && isExportRequest(text)) {
      var fmt = text.toLowerCase().indexOf("csv") !== -1 ? "CSV" : "Excel";
      triggerExport(lastExportInfo, fmt);
      $input.value = "";
      $input.style.height = "auto";
      $sendBtn.disabled = true;
      appendBubble(text, "user");
      appendBubble("Starting your " + fmt + " download\u2026", "assistant");
      scrollToBottom();
      return;
    }

    sending = true;
    $sendBtn.disabled = true;
    $input.value = "";
    $input.style.height = "auto";

    // Clear welcome if present
    var welcome = $messages.querySelector(".ai-chat-welcome");
    if (welcome) welcome.remove();

    appendBubble(text, "user");
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

        // Store export info for follow-up download requests
        lastExportInfo = data.export_info || null;

        // Show assistant response
        appendAssistantMessage(data.answer, {
          sources: data.sources,
          suggested_questions: data.suggested_questions,
          confidence: data.confidence,
          latency_ms: data.latency_ms,
          short_circuited: data.short_circuited,
          export_info: data.export_info,
        });

        scrollToBottom();

        // Refresh sessions sidebar if expanded
        if (expanded && sessionsLoaded) loadSessions();
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

  // ─── Export detection ──────────────────────────────────────────────────────
  function isExportRequest(text) {
    var t = (text || "").toLowerCase();
    var keywords = ["download", "export", "excel", "csv", "xlsx", "spreadsheet"];
    for (var i = 0; i < keywords.length; i++) {
      if (t.indexOf(keywords[i]) !== -1) return true;
    }
    return false;
  }

  function triggerExport(exportInfo, fileType) {
    if (!exportInfo || !exportInfo.doctype) return;
    var url = "/api/method/ai_hrms_suite.api.chatbot.export_chat_data"
      + "?doctype=" + encodeURIComponent(exportInfo.doctype)
      + "&filters=" + encodeURIComponent(JSON.stringify(exportInfo.filters || {}))
      + "&fields=" + encodeURIComponent(JSON.stringify(exportInfo.fields || []))
      + "&file_type=" + encodeURIComponent(fileType || "Excel");
    window.open(url, "_blank");
  }

  // ─── Bubble rendering ─────────────────────────────────────────────────────
  function appendBubble(text, role) {
    var el = document.createElement("div");
    el.className = "ai-chat-msg ai-chat-msg-" + role;
    el.textContent = text;
    $messages.appendChild(el);
    return el;
  }

  function appendAssistantMessage(answer, opts) {
    opts = opts || {};

    var wrapper = document.createElement("div");
    wrapper.className = "ai-chat-msg-wrapper";

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
        html += '<span class="ai-chat-meta-dot ' + opts.confidence + '"></span> ' + opts.confidence;
      }
      if (opts.latency_ms) {
        html += (html ? " \u00B7 " : "") + opts.latency_ms + "ms";
      }
      if (opts.short_circuited) {
        html += (html ? " \u00B7 " : "") + "\u26A1 fast";
      }
      meta.innerHTML = html;
      wrapper.appendChild(meta);
    }

    // Export buttons — show when export_info is present
    var expInfo = opts.export_info;
    if (expInfo && expInfo.doctype && expInfo.record_count > 0) {
      var exportBar = document.createElement("div");
      exportBar.className = "ai-chat-export-bar";

      var excelBtn = document.createElement("button");
      excelBtn.className = "ai-chat-export-btn ai-chat-export-excel";
      excelBtn.innerHTML = ICON_DOWNLOAD + " Download Excel";
      excelBtn.addEventListener("click", function () {
        triggerExport(expInfo, "Excel");
      });

      var csvBtn = document.createElement("button");
      csvBtn.className = "ai-chat-export-btn ai-chat-export-csv";
      csvBtn.innerHTML = ICON_DOWNLOAD + " Download CSV";
      csvBtn.addEventListener("click", function () {
        triggerExport(expInfo, "CSV");
      });

      exportBar.appendChild(excelBtn);
      exportBar.appendChild(csvBtn);
      wrapper.appendChild(exportBar);
    }

    // Suggested questions
    var suggestions = opts.suggested_questions || [];
    // Auto-add export suggestion if we have exportable data
    if (expInfo && expInfo.doctype && expInfo.record_count > 0 && suggestions.length < 3) {
      suggestions = suggestions.slice(); // clone
      suggestions.push("Download this data as Excel");
    }

    if (suggestions.length) {
      var container = document.createElement("div");
      container.className = "ai-chat-suggestions";
      for (var i = 0; i < suggestions.length; i++) {
        var chip = document.createElement("span");
        chip.className = "ai-chat-suggestion-chip";
        chip.textContent = suggestions[i];
        chip.setAttribute("data-q", suggestions[i]);
        container.appendChild(chip);
      }
      wrapper.appendChild(container);
      bindSuggestionChips(wrapper);
    }

    $messages.appendChild(wrapper);
  }

  // ─── Typing indicator ─────────────────────────────────────────────────────
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

  // ─── Scroll ────────────────────────────────────────────────────────────────
  function scrollToBottom() {
    setTimeout(function () {
      $messages.scrollTop = $messages.scrollHeight;
    }, 50);
  }

  // ─── Boot ──────────────────────────────────────────────────────────────────
  if (typeof frappe !== "undefined" && frappe.ready) {
    frappe.ready(function () { init(); });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      var interval = setInterval(function () {
        if (typeof frappe !== "undefined" && frappe.boot) {
          clearInterval(interval);
          init();
        }
      }, 500);
    });
  }
})();
