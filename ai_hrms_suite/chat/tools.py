"""
Node 2: Tool Execution — zero LLM cost, pure Frappe API calls.

Each tool is permission-checked and scoped to HRMS modules.
The registry pattern makes it trivial to add agentic action tools in Phase 2.
"""

import re
from typing import Any, Callable

import frappe

from ai_hrms_suite.chat.retriever import (
    get_all_hrms_doctypes,
    safe_field_summary,
    sanitize_fields,
    sanitize_filters,
    truncate_value,
    validate_doctype_in_hrms,
)


# ─── Public entry point ──────────────────────────────────────────────────────

def execute_tools(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Execute tool calls produced by the intent node.

    Returns a flat list of context items (dicts) consumed by the response node.
    Max 4 tool calls per question (enforced by schema + here).
    """
    results: list[dict[str, Any]] = []
    for tc in (tool_calls or [])[:4]:
        tool_name = tc.get("tool", "")
        params = tc.get("params") or {}
        handler = _TOOL_REGISTRY.get(tool_name)
        if not handler:
            results.append(
                _error_item(f"tool:{tool_name}", f"Unknown tool: {tool_name}")
            )
            continue
        try:
            items = handler(params)
            results.extend(items)
        except Exception as e:
            results.append(
                _error_item(f"tool:{tool_name}", str(e)[:200])
            )
    return results


# ─── Tool implementations ────────────────────────────────────────────────────

def _tool_search_meta(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Search DocType metadata within HRMS modules."""
    query = str(params.get("query", "")).strip()
    limit = min(max(int(params.get("limit", 5)), 1), 8)
    if not query:
        return []

    hrms_doctypes = get_all_hrms_doctypes()
    if not hrms_doctypes:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    # Build SQL scoped to HRMS doctypes
    dt_placeholders = ", ".join(["%s"] * len(hrms_doctypes))
    like_clauses: list[str] = []
    like_params: list[str] = []
    for t in tokens:
        like_clauses.append(
            "(dt.name LIKE %s OR dt.description LIKE %s OR df.label LIKE %s)"
        )
        like_params.extend([f"%{t}%"] * 3)

    sql = f"""
        SELECT DISTINCT dt.name, dt.module, dt.description
        FROM `tabDocType` dt
        LEFT JOIN `tabDocField` df ON df.parent = dt.name
        WHERE dt.name IN ({dt_placeholders})
          AND ({" OR ".join(like_clauses)})
        LIMIT %s
    """
    sql_params = list(hrms_doctypes) + like_params + [limit]
    rows = frappe.db.sql(sql, tuple(sql_params), as_dict=True)

    results: list[dict[str, Any]] = []
    for row in rows:
        if not frappe.has_permission(row["name"], "read"):
            continue
        meta = frappe.get_meta(row["name"])
        results.append(
            {
                "source_id": f"meta:{row['name']}",
                "type": "doctype_meta",
                "doctype": row["name"],
                "module": row["module"],
                "description": row["description"] or "",
                "fields": safe_field_summary(meta),
            }
        )
    return results


def _tool_list_records(params: dict[str, Any]) -> list[dict[str, Any]]:
    """List records from a DocType with permission + filter sanitization."""
    doctype = str(params.get("doctype", "")).strip()
    if not doctype:
        return []
    if not validate_doctype_in_hrms(doctype):
        return [_error_item(f"list:{doctype}", f"'{doctype}' not in HRMS modules.")]
    if not frappe.db.exists("DocType", doctype):
        return [_error_item(f"list:{doctype}", f"DocType '{doctype}' does not exist.")]
    if not frappe.has_permission(doctype, "read"):
        return [_error_item(f"list:{doctype}", f"No read permission for {doctype}.")]

    meta = frappe.get_meta(doctype)
    filters = sanitize_filters(meta, params.get("filters") or {})
    fields = sanitize_fields(meta, params.get("fields") or [])
    limit = min(max(int(params.get("limit", 5)), 1), 10)

    rows = frappe.get_list(
        doctype,
        filters=filters,
        fields=fields,
        limit_page_length=limit,
        ignore_permissions=False,
    )
    results: list[dict[str, Any]] = []
    for r in rows:
        safe_row = {k: truncate_value(v) for k, v in r.items()}
        results.append(
            {
                "source_id": f"record:{doctype}:{safe_row.get('name', '')}",
                "type": "record",
                "doctype": doctype,
                "data": safe_row,
            }
        )
    return results


def _tool_count_records(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Count records matching filters."""
    doctype = str(params.get("doctype", "")).strip()
    if not doctype:
        return []
    if not validate_doctype_in_hrms(doctype):
        return [_error_item(f"count:{doctype}", f"'{doctype}' not in HRMS modules.")]
    if not frappe.db.exists("DocType", doctype):
        return [_error_item(f"count:{doctype}", f"DocType '{doctype}' does not exist.")]
    if not frappe.has_permission(doctype, "read"):
        return [_error_item(f"count:{doctype}", f"No read permission for {doctype}.")]

    meta = frappe.get_meta(doctype)
    filters = sanitize_filters(meta, params.get("filters") or {})
    count = frappe.db.count(doctype, filters=filters)
    return [
        {
            "source_id": f"count:{doctype}",
            "type": "count",
            "doctype": doctype,
            "filters_used": filters,
            "count": count,
        }
    ]


def _tool_get_record(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Get a single record by name."""
    doctype = str(params.get("doctype", "")).strip()
    name = str(params.get("name", "")).strip()
    if not doctype or not name:
        return []
    if not validate_doctype_in_hrms(doctype):
        return [_error_item(f"get:{doctype}", f"'{doctype}' not in HRMS modules.")]
    if not frappe.db.exists(doctype, name):
        return [_error_item(f"get:{doctype}:{name}", f"{doctype}/{name} not found.")]
    if not frappe.has_permission(doctype, "read", doc=name):
        return [
            _error_item(
                f"get:{doctype}:{name}",
                f"No read permission for {doctype}/{name}.",
            )
        ]

    meta = frappe.get_meta(doctype)
    fields = sanitize_fields(meta, params.get("fields") or [])
    doc = frappe.get_doc(doctype, name)
    data: dict[str, Any] = {}
    for f in fields:
        val = getattr(doc, f, None)
        data[f] = truncate_value(val)

    return [
        {
            "source_id": f"record:{doctype}:{name}",
            "type": "record",
            "doctype": doctype,
            "name": name,
            "data": data,
        }
    ]


# ─── Registry ────────────────────────────────────────────────────────────────
# Phase 2: add action tools here (create_leave, submit_expense, etc.)

_TOOL_REGISTRY: dict[str, Callable] = {
    "search_meta": _tool_search_meta,
    "list_records": _tool_list_records,
    "count_records": _tool_count_records,
    "get_record": _tool_get_record,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tokenize(query: str) -> list[str]:
    """Split query into searchable tokens (unique, length > 2, max 6)."""
    tokens = [t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 2]
    return list(dict.fromkeys(tokens))[:6]


def _error_item(source_id: str, error: str) -> dict[str, Any]:
    return {"source_id": f"error:{source_id}", "type": "error", "error": error}
