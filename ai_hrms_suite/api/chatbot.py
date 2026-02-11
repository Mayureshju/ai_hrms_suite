"""
Whitelisted API endpoints for the HRMS AI Chatbot.

All endpoints require login (Frappe session).
Session ownership is enforced — users can only access their own sessions.
"""

import json
import frappe

from ai_hrms_suite.chat.service import ask_hrms
from ai_hrms_suite.chat.retriever import validate_doctype_in_hrms


# ─── Session Management ──────────────────────────────────────────────────────


@frappe.whitelist()
def list_sessions(limit: int = 50):
    """List chat sessions for the current user, most recent first."""
    rows = frappe.get_all(
        "AI Chat Session",
        filters={"user": frappe.session.user},
        fields=["name", "title", "status", "last_message_on", "creation"],
        order_by="last_message_on desc, creation desc",
        limit=int(limit),
    )
    return {"sessions": rows}


@frappe.whitelist()
def create_session(title: str | None = None):
    """Create a new chat session for the current user."""
    doc = frappe.new_doc("AI Chat Session")
    doc.user = frappe.session.user
    doc.title = (title or "New Chat")[:140]
    doc.status = "Active"
    doc.save(ignore_permissions=True)
    return {"session_id": doc.name, "title": doc.title}


@frappe.whitelist()
def rename_session(session_id: str, title: str):
    """Rename a chat session."""
    _assert_session_owner(session_id)
    title = (title or "").strip()[:140]
    if not title:
        frappe.throw("Title is required.")
    frappe.db.set_value("AI Chat Session", session_id, "title", title)
    return {"ok": True}


@frappe.whitelist()
def delete_session(session_id: str):
    """Delete a chat session and all its messages."""
    _assert_session_owner(session_id)
    # Delete child messages first
    frappe.db.delete("AI Chat Message", filters={"session": session_id})
    frappe.delete_doc("AI Chat Session", session_id, ignore_permissions=True)
    return {"ok": True}


# ─── Chat ────────────────────────────────────────────────────────────────────


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
            tools_used, latency_ms, action_plan, export_info
        }
    """
    return ask_hrms(question=question, session_id=session_id)


@frappe.whitelist()
def get_messages(session_id: str, limit: int = 50):
    """Fetch messages for a chat session (newest last)."""
    _assert_session_owner(session_id)

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
        limit=int(limit),
    )
    return {"messages": list(reversed(rows))}


# ─── Agentic: Confirm Action ─────────────────────────────────────────────────


@frappe.whitelist()
def confirm_action(session_id: str, message_id: str):
    """
    Execute a pending action plan stored in a chat message's plan_json.

    The action plan is prepared by the `prepare_action` tool during
    intent analysis. This endpoint validates and executes it.
    """
    _assert_session_owner(session_id)

    msg = frappe.get_doc("AI Chat Message", message_id)
    if msg.session != session_id:
        frappe.throw("Message does not belong to this session.")
    if msg.role != "assistant":
        frappe.throw("Only assistant messages can have action plans.")

    plan_raw = msg.plan_json or ""
    if not plan_raw:
        frappe.throw("No action plan found in this message.")

    try:
        intent_data = json.loads(plan_raw)
    except json.JSONDecodeError:
        frappe.throw("Invalid action plan data.")

    action = intent_data.get("action")
    if not action or not isinstance(action, dict):
        frappe.throw("No executable action found in the plan.")

    action_type = action.get("action_type", "")
    doctype = action.get("doctype", "")
    values = action.get("values") or {}

    if action_type == "create":
        return _execute_create(doctype, values, session_id)
    elif action_type == "submit":
        doc_name = action.get("name", "")
        return _execute_submit(doctype, doc_name, session_id)
    else:
        frappe.throw(f"Unsupported action type: {action_type}")


def _execute_create(doctype: str, values: dict, session_id: str) -> dict:
    """Create a new document from action plan values."""
    if not doctype:
        frappe.throw("DocType is required for create action.")
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(f"You don't have permission to create {doctype}.")

    doc = frappe.new_doc(doctype)
    for field, val in values.items():
        if hasattr(doc, field):
            doc.set(field, val)
    doc.save()

    # Save confirmation message
    _save_action_result(session_id, "create", doctype, doc.name)

    return {
        "ok": True,
        "action": "create",
        "doctype": doctype,
        "name": doc.name,
        "message": f"Created {doctype}: {doc.name}",
    }


def _execute_submit(doctype: str, name: str, session_id: str) -> dict:
    """Submit an existing document."""
    if not name:
        frappe.throw("Document name is required for submit action.")
    if not frappe.has_permission(doctype, "submit"):
        frappe.throw(f"You don't have permission to submit {doctype}.")

    doc = frappe.get_doc(doctype, name)
    doc.submit()

    _save_action_result(session_id, "submit", doctype, name)

    return {
        "ok": True,
        "action": "submit",
        "doctype": doctype,
        "name": name,
        "message": f"Submitted {doctype}: {name}",
    }


def _save_action_result(session_id: str, action: str, doctype: str, name: str):
    """Save a system message recording the executed action."""
    msg = frappe.new_doc("AI Chat Message")
    msg.session = session_id
    msg.role = "assistant"
    msg.content = f"\u2705 Action completed: {action} {doctype} \u2192 {name}"
    msg.status = "Success"
    msg.save(ignore_permissions=True)


# ─── Export: Excel / CSV Download ────────────────────────────────────────────


@frappe.whitelist()
def export_chat_data(
    doctype: str,
    filters: str = "{}",
    fields: str = "[]",
    file_type: str = "Excel",
):
    """
    Export HRMS data queried by the chatbot as Excel or CSV.

    Called from the chatbot UI when user clicks "Download as Excel/CSV".
    Uses the same doctype + filters that the chatbot used to answer the query.
    """
    from frappe.utils.xlsxutils import make_xlsx

    doctype = (doctype or "").strip()
    if not doctype:
        frappe.throw("DocType is required.")
    if not validate_doctype_in_hrms(doctype):
        frappe.throw(f"'{doctype}' is not an HRMS DocType.")
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(f"No read permission for {doctype}.")

    # Parse JSON args
    try:
        parsed_filters = json.loads(filters) if isinstance(filters, str) else filters
    except (json.JSONDecodeError, TypeError):
        parsed_filters = {}

    try:
        parsed_fields = json.loads(fields) if isinstance(fields, str) else fields
    except (json.JSONDecodeError, TypeError):
        parsed_fields = []

    # Ensure we have fields — pull from DocType meta if not provided
    meta = frappe.get_meta(doctype)
    if not parsed_fields or not isinstance(parsed_fields, list):
        parsed_fields = ["name"] + [
            f.fieldname
            for f in meta.fields
            if f.fieldtype not in (
                "Section Break", "Column Break", "Tab Break",
                "Table", "HTML", "Button", "Fold",
                "Attach", "Attach Image", "Geolocation",
            )
            and f.fieldname
            and not f.hidden
        ]

    if "name" not in parsed_fields:
        parsed_fields.insert(0, "name")

    # Sanitize field names against meta
    valid_fieldnames = {f.fieldname for f in meta.fields}
    valid_fieldnames.add("name")
    parsed_fields = [f for f in parsed_fields if f in valid_fieldnames]

    if not parsed_fields:
        parsed_fields = ["name"]

    # Query data (max 500 rows)
    rows = frappe.get_list(
        doctype,
        filters=parsed_filters,
        fields=parsed_fields,
        limit_page_length=500,
        ignore_permissions=False,
    )

    # Build label headers
    field_labels = []
    for fname in parsed_fields:
        if fname == "name":
            field_labels.append("ID")
        else:
            field_meta = meta.get_field(fname)
            field_labels.append(field_meta.label if field_meta else fname)

    # Build data matrix
    data = [field_labels]
    for row in rows:
        data.append([row.get(f, "") for f in parsed_fields])

    file_type = (file_type or "Excel").strip()
    title = f"{doctype} Export"

    if file_type == "CSV":
        from frappe.utils.csvutils import build_csv_response

        build_csv_response(data, title)
    else:
        xlsx_file = make_xlsx(data, title)
        frappe.response["filename"] = f"{title}.xlsx"
        frappe.response["filecontent"] = xlsx_file.getvalue()
        frappe.response["type"] = "binary"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _assert_session_owner(session_id: str):
    """Ensure the current user owns the session."""
    if not frappe.db.exists("AI Chat Session", session_id):
        frappe.throw("Session not found.")
    owner = frappe.db.get_value("AI Chat Session", session_id, "user")
    if owner != frappe.session.user and not frappe.utils.cint(
        frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
        and frappe.has_permission("AI Chat Session", "read")
    ):
        frappe.throw("Not permitted to access this chat session.")
