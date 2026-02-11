/**
 * AI HRMS Chat — Full-page view with session sidebar
 *
 * Layout: [Sidebar (sessions list)] | [Chat Area (messages + input)]
 * Features: session CRUD, agentic action confirmation, suggested questions
 */
frappe.pages["ai-chat"].on_page_load = function (wrapper) {
  new AIChatPage(wrapper);
};

class AIChatPage {
  constructor(wrapper) {
    this.wrapper = wrapper;
    this.sessionId = null;
    this.sending = false;
    this.sessions = [];

    this.buildLayout();
    this.bindEvents();
    this.loadSessions();
  }

  // ─── Build DOM ────────────────────────────────────────────────────────────
  buildLayout() {
    $(this.wrapper).find(".page-content").remove();
    $(this.wrapper).find(".layout-main-section-wrapper").remove();

    const page = $(this.wrapper);
    page.find(".page-head").hide();

    const html = `
      <div class="aic-root">
        <!-- Sidebar -->
        <div class="aic-sidebar">
          <div class="aic-sidebar-header">
            <div class="aic-logo">
              <svg class="aic-logo-icon" viewBox="0 0 24 24" width="28" height="28">
                <path d="M12 2L14.09 8.26L20 9.27L15.55 13.97L16.91 20L12 16.9L7.09 20L8.45 13.97L4 9.27L9.91 8.26L12 2Z" fill="currentColor"/>
              </svg>
              <span class="aic-logo-text">AI HRMS Assistant</span>
            </div>
          </div>

          <div class="aic-sidebar-actions">
            <button class="aic-new-chat-btn" title="New chat">
              <svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>
              <span>New chat</span>
            </button>
          </div>

          <div class="aic-search-box">
            <input type="text" class="aic-search-input" placeholder="Search chats..." />
          </div>

          <div class="aic-sidebar-label">Your chats</div>
          <div class="aic-session-list"></div>
        </div>

        <!-- Main Chat Area -->
        <div class="aic-main">
          <div class="aic-main-header">
            <span class="aic-main-title">AI HRMS Assistant</span>
            <div class="aic-main-header-actions">
              <button class="aic-toggle-sidebar-btn" title="Toggle sidebar">
                <svg viewBox="0 0 24 24" width="18" height="18"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" fill="currentColor"/></svg>
              </button>
            </div>
          </div>

          <div class="aic-messages"></div>

          <div class="aic-input-area">
            <div class="aic-input-wrapper">
              <textarea class="aic-input" placeholder="Ask anything about HRMS…" rows="1"></textarea>
              <button class="aic-send-btn" disabled title="Send">
                <svg viewBox="0 0 24 24" width="18" height="18"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" fill="currentColor"/></svg>
              </button>
            </div>
            <div class="aic-input-hint">Press Enter to send, Shift+Enter for new line</div>
          </div>
        </div>
      </div>
    `;

    page.append(html);

    // Cache DOM refs
    this.$root = page.find(".aic-root");
    this.$sidebar = page.find(".aic-sidebar");
    this.$sessionList = page.find(".aic-session-list");
    this.$messages = page.find(".aic-messages");
    this.$input = page.find(".aic-input");
    this.$sendBtn = page.find(".aic-send-btn");
    this.$mainTitle = page.find(".aic-main-title");
    this.$searchInput = page.find(".aic-search-input");

    // Show welcome
    this.showWelcome();
  }

  // ─── Events ───────────────────────────────────────────────────────────────
  bindEvents() {
    const self = this;

    // New chat
    this.$root.find(".aic-new-chat-btn").on("click", () => self.newChat());

    // Toggle sidebar (mobile)
    this.$root.find(".aic-toggle-sidebar-btn").on("click", () => {
      self.$sidebar.toggleClass("aic-sidebar-open");
    });

    // Send
    this.$sendBtn.on("click", () => self.sendMessage());

    // Input
    this.$input.on("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        self.sendMessage();
      }
    });

    this.$input.on("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
      self.$sendBtn.prop("disabled", !this.value.trim() || self.sending);
    });

    // Search sessions
    this.$searchInput.on("input", function () {
      self.filterSessions(this.value);
    });
  }

  // ─── Sessions ─────────────────────────────────────────────────────────────
  loadSessions() {
    const self = this;
    frappe.call({
      method: "ai_hrms_suite.api.chatbot.list_sessions",
      args: { limit: 50 },
      async: true,
      callback(r) {
        if (!r || !r.message) return;
        self.sessions = r.message.sessions || [];
        self.renderSessionList();
      },
    });
  }

  renderSessionList() {
    const self = this;
    this.$sessionList.empty();

    if (!this.sessions.length) {
      this.$sessionList.html('<div class="aic-no-sessions">No chats yet</div>');
      return;
    }

    this.sessions.forEach((s) => {
      const isActive = s.name === self.sessionId;
      const timeAgo = frappe.datetime.prettyDate(s.last_message_on || s.creation);
      const $item = $(`
        <div class="aic-session-item ${isActive ? "active" : ""}" data-id="${s.name}">
          <div class="aic-session-item-content">
            <div class="aic-session-title">${frappe.utils.escape_html(s.title || "New Chat")}</div>
            <div class="aic-session-time">${timeAgo}</div>
          </div>
          <div class="aic-session-actions">
            <button class="aic-session-delete-btn" title="Delete" data-id="${s.name}">
              <svg viewBox="0 0 24 24" width="14" height="14"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
            </button>
          </div>
        </div>
      `);

      // Click to open session
      $item.find(".aic-session-item-content").on("click", () => {
        self.openSession(s.name, s.title);
      });

      // Delete
      $item.find(".aic-session-delete-btn").on("click", (e) => {
        e.stopPropagation();
        self.deleteSession(s.name);
      });

      self.$sessionList.append($item);
    });
  }

  filterSessions(query) {
    const q = (query || "").toLowerCase().trim();
    this.$sessionList.find(".aic-session-item").each(function () {
      const title = $(this).find(".aic-session-title").text().toLowerCase();
      $(this).toggle(!q || title.includes(q));
    });
  }

  newChat() {
    this.sessionId = null;
    this.$messages.empty();
    this.$input.val("").css("height", "auto");
    this.$sendBtn.prop("disabled", true);
    this.$mainTitle.text("AI HRMS Assistant");
    this.showWelcome();
    this.renderSessionList();
    // Close sidebar on mobile
    this.$sidebar.removeClass("aic-sidebar-open");
  }

  openSession(sessionId, title) {
    this.sessionId = sessionId;
    this.$mainTitle.text(title || "AI HRMS Assistant");
    this.$messages.empty();
    this.renderSessionList();
    this.loadMessages(sessionId);
    this.$sidebar.removeClass("aic-sidebar-open");
  }

  deleteSession(sessionId) {
    const self = this;
    frappe.confirm(
      "Delete this chat and all its messages?",
      () => {
        frappe.call({
          method: "ai_hrms_suite.api.chatbot.delete_session",
          args: { session_id: sessionId },
          async: true,
          callback() {
            // If we're deleting the active session, reset
            if (self.sessionId === sessionId) {
              self.newChat();
            }
            self.loadSessions();
            frappe.show_alert({ message: "Chat deleted", indicator: "green" });
          },
        });
      }
    );
  }

  // ─── Messages ─────────────────────────────────────────────────────────────
  loadMessages(sessionId) {
    const self = this;
    frappe.call({
      method: "ai_hrms_suite.api.chatbot.get_messages",
      args: { session_id: sessionId, limit: 50 },
      async: true,
      callback(r) {
        if (!r || !r.message || !r.message.messages) return;
        const msgs = r.message.messages;
        if (!msgs.length) {
          self.showWelcome();
          return;
        }

        self.$messages.empty();
        msgs.forEach((m) => {
          if (m.role === "user") {
            self.appendBubble(m.content, "user");
          } else if (m.role === "assistant") {
            self.appendAssistantMessage(m.content, {
              sources_json: m.sources_json,
              latency_ms: m.latency_ms,
              plan_json: m.plan_json,
              message_id: m.name,
            });
          }
        });
        self.scrollToBottom();
      },
    });
  }

  // ─── Welcome ──────────────────────────────────────────────────────────────
  showWelcome() {
    const userName = frappe.session.user_fullname || frappe.session.user;
    const firstName = userName.split(" ")[0];

    this.$messages.html(`
      <div class="aic-welcome">
        <div class="aic-welcome-sparkle">
          <svg viewBox="0 0 24 24" width="64" height="64">
            <defs>
              <linearGradient id="aic-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#7c3aed;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#a78bfa;stop-opacity:1" />
              </linearGradient>
            </defs>
            <path d="M12 2L14.09 8.26L20 9.27L15.55 13.97L16.91 20L12 16.9L7.09 20L8.45 13.97L4 9.27L9.91 8.26L12 2Z" fill="url(#aic-grad)"/>
          </svg>
        </div>
        <h2 class="aic-welcome-title">Hey, ${frappe.utils.escape_html(firstName)}</h2>
        <p class="aic-welcome-subtitle">How can I help you today?</p>
        <div class="aic-suggestions">
          <span class="aic-suggestion-chip" data-q="How do I apply for leave?">How do I apply for leave?</span>
          <span class="aic-suggestion-chip" data-q="Show me pending leave applications">Pending leave applications</span>
          <span class="aic-suggestion-chip" data-q="How does payroll processing work?">How does payroll work?</span>
          <span class="aic-suggestion-chip" data-q="Create a leave application for me">Create a leave application</span>
          <span class="aic-suggestion-chip" data-q="How many employees are in the company?">Employee count</span>
          <span class="aic-suggestion-chip" data-q="What attendance modes are available?">Attendance modes</span>
        </div>
      </div>
    `);

    const self = this;
    this.$messages.find(".aic-suggestion-chip").on("click", function () {
      self.$input.val($(this).data("q")).trigger("input");
      self.sendMessage();
    });
  }

  // ─── Send ─────────────────────────────────────────────────────────────────
  sendMessage() {
    const text = (this.$input.val() || "").trim();
    if (!text || this.sending) return;

    this.sending = true;
    this.$sendBtn.prop("disabled", true);
    this.$input.val("").css("height", "auto");

    // Clear welcome
    this.$messages.find(".aic-welcome").remove();

    this.appendBubble(text, "user");
    this.showTyping();
    this.scrollToBottom();

    const self = this;
    frappe.call({
      method: "ai_hrms_suite.api.chatbot.ask",
      args: { question: text, session_id: this.sessionId },
      async: true,
      callback(r) {
        self.hideTyping();
        self.sending = false;
        self.$sendBtn.prop("disabled", !self.$input.val().trim());

        if (!r || !r.message) {
          self.appendBubble("Something went wrong. Please try again.", "error");
          self.scrollToBottom();
          return;
        }

        const data = r.message;

        // Persist session
        if (data.session_id && data.session_id !== self.sessionId) {
          self.sessionId = data.session_id;
          self.loadSessions(); // Refresh sidebar
        }

        // Update header title from first message
        if (self.$mainTitle.text() === "AI HRMS Assistant" && text.length > 0) {
          const autoTitle = text.length > 40 ? text.substring(0, 40) + "…" : text;
          self.$mainTitle.text(autoTitle);
        }

        self.appendAssistantMessage(data.answer, {
          sources: data.sources,
          suggested_questions: data.suggested_questions,
          confidence: data.confidence,
          latency_ms: data.latency_ms,
          short_circuited: data.short_circuited,
          action_plan: data.action_plan,
        });
        self.scrollToBottom();
      },
      error(err) {
        self.hideTyping();
        self.sending = false;
        self.$sendBtn.prop("disabled", !self.$input.val().trim());
        const errMsg = (err && err.message) || "Request failed. Please try again.";
        self.appendBubble(errMsg, "error");
        self.scrollToBottom();
      },
    });
  }

  // ─── Bubbles ──────────────────────────────────────────────────────────────
  appendBubble(text, role) {
    const $el = $(`<div class="aic-msg aic-msg-${role}"></div>`);
    $el.text(text);
    this.$messages.append($el);
    return $el;
  }

  appendAssistantMessage(answer, opts) {
    opts = opts || {};
    const $wrapper = $('<div class="aic-msg-wrapper"></div>');

    // Avatar
    const $avatar = $(`
      <div class="aic-avatar">
        <svg viewBox="0 0 24 24" width="20" height="20">
          <path d="M12 2L14.09 8.26L20 9.27L15.55 13.97L16.91 20L12 16.9L7.09 20L8.45 13.97L4 9.27L9.91 8.26L12 2Z" fill="currentColor"/>
        </svg>
      </div>
    `);
    $wrapper.append($avatar);

    const $content = $('<div class="aic-msg-content"></div>');

    // Main answer bubble — render markdown-like formatting
    const $bubble = $('<div class="aic-msg aic-msg-assistant"></div>');
    $bubble.html(this.formatAnswer(answer || "(No response)"));
    $content.append($bubble);

    // Action plan card (for agentic actions)
    if (opts.action_plan && typeof opts.action_plan === "object") {
      $content.append(this.buildActionCard(opts.action_plan));
    }

    // Check plan_json for action plans loaded from history
    if (opts.plan_json) {
      try {
        const plan = typeof opts.plan_json === "string" ? JSON.parse(opts.plan_json) : opts.plan_json;
        if (plan && plan.action && plan.action.action_type) {
          $content.append(this.buildActionCard(plan.action, opts.message_id));
        }
      } catch (e) { /* ignore parse errors */ }
    }

    // Meta line
    if (opts.confidence || opts.latency_ms) {
      const parts = [];
      if (opts.confidence) {
        parts.push(`<span class="aic-meta-dot ${opts.confidence}"></span> ${opts.confidence}`);
      }
      if (opts.latency_ms) {
        parts.push(`${opts.latency_ms}ms`);
      }
      if (opts.short_circuited) {
        parts.push("⚡ fast");
      }
      $content.append(`<div class="aic-meta">${parts.join(" · ")}</div>`);
    }

    // Suggested questions
    const suggestions = opts.suggested_questions || [];
    if (suggestions.length) {
      const $chips = $('<div class="aic-suggestions"></div>');
      const self = this;
      suggestions.forEach((q) => {
        const $chip = $(`<span class="aic-suggestion-chip"></span>`);
        $chip.text(q);
        $chip.on("click", () => {
          self.$input.val(q).trigger("input");
          self.sendMessage();
        });
        $chips.append($chip);
      });
      $content.append($chips);
    }

    $wrapper.append($content);
    this.$messages.append($wrapper);
  }

  formatAnswer(text) {
    // Convert basic markdown to HTML
    let html = frappe.utils.escape_html(text);
    // Bold: **text** or __text__
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__(.*?)__/g, "<strong>$1</strong>");
    // Bullet points: lines starting with - or •
    html = html.replace(/^[\-•]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    // Numbered lists: lines starting with 1. 2. etc
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
    // Links: /app/something
    html = html.replace(/(\/app\/[\w-]+)/g, '<a href="$1" class="aic-link">$1</a>');
    // Newlines to <br>
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  buildActionCard(action, messageId) {
    const doctype = action.doctype || "";
    const actionType = action.action_type || "create";
    const values = action.values || {};
    const preview = action.preview || "";

    let fieldsHtml = "";
    Object.entries(values).forEach(([key, val]) => {
      fieldsHtml += `
        <div class="aic-action-field">
          <span class="aic-action-field-label">${frappe.utils.escape_html(key)}</span>
          <span class="aic-action-field-value">${frappe.utils.escape_html(String(val))}</span>
        </div>
      `;
    });

    const $card = $(`
      <div class="aic-action-card">
        <div class="aic-action-card-header">
          <span class="aic-action-badge">${actionType.toUpperCase()}</span>
          <span class="aic-action-doctype">${frappe.utils.escape_html(doctype)}</span>
        </div>
        ${preview ? `<div class="aic-action-preview">${frappe.utils.escape_html(preview)}</div>` : ""}
        ${fieldsHtml ? `<div class="aic-action-fields">${fieldsHtml}</div>` : ""}
        <div class="aic-action-buttons">
          <button class="btn btn-primary btn-sm aic-confirm-action-btn">
            ✅ Confirm & Execute
          </button>
          <button class="btn btn-default btn-sm aic-cancel-action-btn">
            Cancel
          </button>
        </div>
      </div>
    `);

    const self = this;
    $card.find(".aic-confirm-action-btn").on("click", function () {
      $(this).prop("disabled", true).text("Executing...");
      self.confirmAction(messageId);
    });

    $card.find(".aic-cancel-action-btn").on("click", function () {
      $card.slideUp(200, () => $card.remove());
      self.appendBubble("Action cancelled.", "system");
      self.scrollToBottom();
    });

    return $card;
  }

  confirmAction(messageId) {
    if (!this.sessionId || !messageId) {
      frappe.show_alert({ message: "Cannot confirm: missing context.", indicator: "red" });
      return;
    }

    const self = this;
    frappe.call({
      method: "ai_hrms_suite.api.chatbot.confirm_action",
      args: { session_id: this.sessionId, message_id: messageId },
      async: true,
      callback(r) {
        if (!r || !r.message) {
          self.appendBubble("Action failed.", "error");
          self.scrollToBottom();
          return;
        }
        const result = r.message;
        const msg = result.message || `${result.action} ${result.doctype}: ${result.name}`;
        self.appendBubble(`✅ ${msg}`, "system");

        // Remove the action card
        self.$messages.find(".aic-action-card").last().slideUp(200);
        self.scrollToBottom();
      },
      error(err) {
        const errMsg = (err && err._server_messages)
          ? JSON.parse(err._server_messages)[0]
          : "Action execution failed.";
        self.appendBubble(`❌ ${errMsg}`, "error");
        self.$messages.find(".aic-confirm-action-btn").last().prop("disabled", false).text("✅ Confirm & Execute");
        self.scrollToBottom();
      },
    });
  }

  // ─── Typing ───────────────────────────────────────────────────────────────
  showTyping() {
    if (this.$messages.find(".aic-typing").length) return;
    this.$messages.append(`
      <div class="aic-msg-wrapper aic-typing">
        <div class="aic-avatar">
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path d="M12 2L14.09 8.26L20 9.27L15.55 13.97L16.91 20L12 16.9L7.09 20L8.45 13.97L4 9.27L9.91 8.26L12 2Z" fill="currentColor"/>
          </svg>
        </div>
        <div class="aic-msg-content">
          <div class="aic-msg aic-msg-assistant aic-typing-dots">
            <span class="aic-dot"></span>
            <span class="aic-dot"></span>
            <span class="aic-dot"></span>
          </div>
        </div>
      </div>
    `);
  }

  hideTyping() {
    this.$messages.find(".aic-typing").remove();
  }

  // ─── Scroll ───────────────────────────────────────────────────────────────
  scrollToBottom() {
    const el = this.$messages[0];
    if (el) {
      setTimeout(() => { el.scrollTop = el.scrollHeight; }, 50);
    }
  }
}
