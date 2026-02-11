"""
HRMS Chatbot orchestrator — 3-node hybrid pipeline with cost optimization.

Flow:
    User Query
        │
        ▼
    Node 1 · Intent Analysis  (cheap model — e.g. gpt-4o-mini)
        │
        ├─ short-circuit? ──► return short_answer (skip Node 2 + 3)
        │
        ▼
    Node 2 · Tool Execution  (zero LLM cost — pure Frappe API)
        │
        ▼
    Node 3 · Response Gen    (smart model — e.g. Claude 3.5 Sonnet)
        │
        ▼
    Final Answer
"""

import json
import time
from typing import Any, Optional

import frappe

from ai_hrms_suite.chat.intent import analyze_intent
from ai_hrms_suite.chat.tools import execute_tools
from ai_hrms_suite.chat.responder import generate_response


# ─── Short-circuit thresholds ─────────────────────────────────────────────────

_SHORT_CIRCUIT_CONFIDENCE = 0.9
_SHORT_CIRCUIT_INTENTS = frozenset({"greeting", "clarification"})


# ─── Session helpers ──────────────────────────────────────────────────────────

def _get_recent_messages(session_id: str, limit: int = 6) -> list[dict[str, Any]]:
    rows = frappe.get_all(
        "AI Chat Message",
        filters={"session": session_id},
        fields=["role", "content"],
        order_by="creation desc",
        limit=limit,
    )
    return list(reversed(rows))


def _ensure_session(session_id: Optional[str]) -> str:
    """Return an existing (owned) session or create a new one."""
    if session_id and frappe.db.exists("AI Chat Session", session_id):
        doc = frappe.get_doc("AI Chat Session", session_id)
        if doc.user != frappe.session.user and not frappe.has_permission(
            "AI Chat Session", "read", doc=doc
        ):
            frappe.throw("Not permitted to access this chat session.")
        return doc.name

    doc = frappe.new_doc("AI Chat Session")
    doc.user = frappe.session.user
    doc.title = "New Chat"
    doc.status = "Active"
    doc.save(ignore_permissions=True)
    return doc.name


# ─── Persistence ──────────────────────────────────────────────────────────────

def _save_message(
    session_id: str,
    role: str,
    content: str,
    status: str = "Success",
    plan_json: str = "",
    context_json: str = "",
    sources_json: str = "",
    llm_result=None,
    error: str = "",
) -> str:
    msg = frappe.new_doc("AI Chat Message")
    msg.session = session_id
    msg.role = role
    msg.content = content or ""
    msg.status = status
    msg.plan_json = plan_json or ""
    msg.context_json = context_json or ""
    msg.sources_json = sources_json or ""
    msg.error = error or ""
    if llm_result:
        msg.provider = getattr(llm_result, "provider", "")
        msg.model = getattr(llm_result, "model", "")
        msg.tokens_in = int(getattr(llm_result, "tokens_in", 0) or 0)
        msg.tokens_out = int(getattr(llm_result, "tokens_out", 0) or 0)
        msg.cost_usd = float(getattr(llm_result, "cost_usd", 0.0) or 0.0)
        msg.latency_ms = int(getattr(llm_result, "latency_ms", 0) or 0)
    msg.save(ignore_permissions=True)
    return msg.name


def _log_run(
    run_type: str,
    llm_result,
    status: str,
    error: str = "",
    cache_hit: bool = False,
):
    log = frappe.new_doc("AI Run Log")
    log.run_type = run_type
    log.provider = getattr(llm_result, "provider", "cache") if llm_result else "cache"
    log.model = getattr(llm_result, "model", "cache") if llm_result else "cache"
    log.tokens_in = int(getattr(llm_result, "tokens_in", 0) or 0) if llm_result else 0
    log.tokens_out = (
        int(getattr(llm_result, "tokens_out", 0) or 0) if llm_result else 0
    )
    log.cost_usd = (
        float(getattr(llm_result, "cost_usd", 0.0) or 0.0) if llm_result else 0.0
    )
    log.latency_ms = (
        int(getattr(llm_result, "latency_ms", 0) or 0) if llm_result else 0
    )
    log.status = status
    log.error = error or ("CACHE_HIT" if cache_hit else "")
    log.save(ignore_permissions=True)


# ─── Short-circuit logic ─────────────────────────────────────────────────────

def _can_short_circuit(intent_data: dict[str, Any]) -> bool:
    """
    Determine if we can skip the expensive Node 3 (response generation).

    Short-circuit when:
      1. Greetings / clarifications with a short_answer already provided.
      2. High-confidence questions with no tools needed + a short_answer.
    Never short-circuit action_request (needs proper confirmation flow).
    """
    confidence = float(intent_data.get("confidence", 0.0))
    intent_type = intent_data.get("intent", "")
    tools = intent_data.get("tools") or []
    short_answer = (intent_data.get("short_answer") or "").strip()

    # Never short-circuit actions — they need the response model for confirmation cards
    if intent_type == "action_request":
        return False

    # Greetings / clarifications — always cheap
    if intent_type in _SHORT_CIRCUIT_INTENTS and short_answer:
        return True

    # High confidence + no tool calls + model provided a direct answer
    if confidence >= _SHORT_CIRCUIT_CONFIDENCE and not tools and short_answer:
        return True

    return False


# ─── Export info extractor ────────────────────────────────────────────────────

def _extract_export_info(
    intent_data: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    If list_records was used and returned records, build export_info
    so the frontend can offer "Download as Excel/CSV".

    Returns: {doctype, filters, fields, record_count} or None
    """
    tools = intent_data.get("tools") or []
    list_tool = None
    for t in tools:
        if t.get("tool") == "list_records":
            list_tool = t
            break

    if not list_tool:
        return None

    # Count how many records the tool actually returned
    record_count = sum(
        1 for r in tool_results if r.get("type") == "record"
    )
    if record_count == 0:
        return None

    params = list_tool.get("params") or {}
    return {
        "doctype": params.get("doctype", ""),
        "filters": params.get("filters") or {},
        "fields": params.get("fields") or [],
        "record_count": record_count,
    }


# ─── Main orchestrator ────────────────────────────────────────────────────────

def ask_hrms(question: str, session_id: Optional[str] = None) -> dict[str, Any]:
    """
    Main entry point: Intent → Tools → Response (with short-circuit).

    Cost breakdown (typical):
        Short-circuited  → ~1 cheap LLM call  (≈ $0.0001)
        Full pipeline    → 1 cheap + 1 smart   (≈ $0.003–0.01)
    """
    if not question or not str(question).strip():
        frappe.throw("Question is required.")

    session_id = _ensure_session(session_id)
    recent_messages = _get_recent_messages(session_id, limit=6)

    # Save user message
    _save_message(session_id, role="user", content=question)

    t0 = time.time()
    intent_data: dict[str, Any] = {}
    tool_results: list[dict[str, Any]] = []
    answer_data: dict[str, Any] = {}
    intent_llm_result = None
    response_llm_result = None
    short_circuited = False

    try:
        # ── Node 1: Intent Analysis (cheap model) ──────────────────────
        intent_out = analyze_intent(question, recent_messages)
        intent_data = intent_out["intent"]
        intent_llm_result = intent_out["llm_result"]
        _log_run(
            "intent_analysis",
            intent_llm_result,
            "Success",
            cache_hit=intent_out["cache_hit"],
        )

        # ── Short-circuit check ────────────────────────────────────────
        if _can_short_circuit(intent_data):
            short_circuited = True
            short_answer = intent_data.get("short_answer", "")
            confidence_val = float(intent_data.get("confidence", 0))
            answer_data = {
                "answer": short_answer,
                "sources": [],
                "suggested_questions": [],
                "confidence": "high" if confidence_val >= 0.9 else "medium",
            }
        else:
            # ── Node 2: Tool Execution (zero LLM cost) ─────────────────
            tool_results = execute_tools(intent_data.get("tools") or [])

            # ── Node 3: Response Generation (smart model) ──────────────
            response_out = generate_response(
                question=question,
                intent=intent_data,
                tool_results=tool_results,
                recent_messages=recent_messages,
            )
            answer_data = response_out["data"]
            response_llm_result = response_out["llm_result"]
            _log_run(
                "response_gen",
                response_llm_result,
                "Success",
                cache_hit=response_out["cache_hit"],
            )

    except Exception as e:
        _save_message(
            session_id=session_id,
            role="assistant",
            content="",
            status="Failed",
            plan_json=json.dumps(intent_data or {}, ensure_ascii=True),
            context_json=json.dumps(tool_results or [], ensure_ascii=True),
            sources_json="[]",
            error=str(e),
        )
        raise

    t1 = time.time()

    # Prefer the response-gen LLM result for message metadata; fall back to intent
    msg_llm_result = response_llm_result or intent_llm_result

    _save_message(
        session_id=session_id,
        role="assistant",
        content=answer_data.get("answer", ""),
        status="Success",
        plan_json=json.dumps(intent_data, ensure_ascii=True),
        context_json=json.dumps(tool_results, ensure_ascii=True),
        sources_json=json.dumps(answer_data.get("sources", []), ensure_ascii=True),
        llm_result=msg_llm_result,
    )

    frappe.db.set_value(
        "AI Chat Session",
        session_id,
        {"last_message_on": frappe.utils.now_datetime()},
        update_modified=True,
    )

    # Build export_info if list_records was used (for Excel/CSV download)
    export_info = _extract_export_info(intent_data, tool_results)

    return {
        "session_id": session_id,
        "answer": answer_data.get("answer", ""),
        "sources": answer_data.get("sources", []),
        "suggested_questions": answer_data.get("suggested_questions", []),
        "confidence": answer_data.get("confidence", "low"),
        "intent": intent_data.get("intent", ""),
        "domain": intent_data.get("domain", ""),
        "short_circuited": short_circuited,
        "tools_used": len(tool_results),
        "latency_ms": int((t1 - t0) * 1000),
        "action_plan": answer_data.get("action_plan"),
        "export_info": export_info,
    }
