"""
Whitelisted API endpoints for the HRMS AI Chatbot.

All endpoints require login (Frappe session).
Session ownership is enforced — users can only access their own sessions.
"""

import frappe

from ai_hrms_suite.chat.service import ask_hrms


@frappe.whitelist()
def create_session(title: str | None = None):
    """Create a new chat session for the current user."""
    doc = frappe.new_doc("AI Chat Session")
    doc.user = frappe.session.user
    doc.title = (title or "New Chat")[:140]
    doc.status = "Active"
    doc.save(ignore_permissions=True)
    return {"session_id": doc.name}


@frappe.whitelist()
def ask(question: str, session_id: str | None = None):
    """
    Ask an HRMS question.

    Runs the 3-node hybrid pipeline:
        Intent (cheap) → Tools (free) → Response (smart, if needed)

    Returns:
        {
            session_id, answer, sources, suggested_questions,
            confidence, intent, domain, short_circuited,
            tools_used, latency_ms
        }
    """
    return ask_hrms(question=question, session_id=session_id)


@frappe.whitelist()
def get_messages(session_id: str, limit: int = 20):
    """Fetch messages for a chat session (newest last)."""
    if not frappe.db.exists("AI Chat Session", session_id):
        frappe.throw("Session not found.")
    session = frappe.get_doc("AI Chat Session", session_id)
    if session.user != frappe.session.user and not frappe.has_permission(
        "AI Chat Session", "read", doc=session
    ):
        frappe.throw("Not permitted to access this chat session.")

    rows = frappe.get_all(
        "AI Chat Message",
        filters={"session": session_id},
        fields=[
            "name",
            "role",
            "content",
            "status",
            "creation",
            "sources_json",
            "plan_json",
            "provider",
            "model",
            "tokens_in",
            "tokens_out",
            "cost_usd",
            "latency_ms",
        ],
        order_by="creation desc",
        limit=limit,
    )
    return {"messages": list(reversed(rows))}
