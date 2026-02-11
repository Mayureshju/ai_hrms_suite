"""
Node 2: Tool Execution — zero LLM cost, pure Frappe API calls.

Each tool is permission-checked and scoped to HRMS modules.
Supports both read-only tools (search, list, count, get) and
agentic action tools (prepare_action) with a two-step confirmation flow.
"""

import re
from typing import Any, Callable

import frappe
from frappe.utils import today, nowdate, get_fullname

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


# ─── Read-Only Tool implementations ──────────────────────────────────────────

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

    # Auto-scope employee-linked DocTypes to current user's employee
    # when no employee/employee_name filter is provided ("my leave balance").
    filters = _auto_scope_employee(meta, doctype, filters)

    # Auto-include key display fields so results are human-readable
    fields = _ensure_display_fields(meta, doctype, fields)

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


# Fields that should always be included when listing certain DocTypes
# so that results are human-readable (names, not just IDs).
_DISPLAY_FIELDS: dict[str, list[str]] = {
    "Employee": ["employee_name", "company", "department", "designation", "status"],
    "Leave Application": ["employee_name", "leave_type", "from_date", "to_date", "status"],
    "Leave Allocation": ["employee_name", "leave_type", "new_leaves_allocated", "total_leaves_allocated"],
    "Leave Ledger Entry": ["employee_name", "leave_type", "leaves", "from_date", "to_date"],
    "Attendance": ["employee_name", "attendance_date", "status"],
    "Expense Claim": ["employee_name", "total_claimed_amount", "status"],
    "Salary Slip": ["employee_name", "posting_date", "gross_pay", "net_pay"],
    "Job Applicant": ["applicant_name", "job_title", "status"],
    "Job Opening": ["job_title", "department", "status"],
}


def _ensure_display_fields(meta, doctype: str, fields: list[str]) -> list[str]:
    """Ensure key display fields are present for known DocTypes."""
    extras = _DISPLAY_FIELDS.get(doctype, [])
    if not extras:
        return fields

    existing = set(fields)
    for f in extras:
        if f not in existing and meta.get_field(f):
            fields.append(f)
    # Keep within the 12-field limit but prioritize display fields
    return fields[:12]


# DocTypes where "employee" filter should auto-scope to current user if empty
_EMPLOYEE_SCOPED_DOCTYPES = frozenset({
    "Leave Allocation", "Leave Application", "Leave Ledger Entry",
    "Attendance", "Attendance Request", "Expense Claim",
    "Salary Slip", "Compensatory Leave Request",
})


def _auto_scope_employee(
    meta, doctype: str, filters: dict[str, Any]
) -> dict[str, Any]:
    """
    For employee-linked DocTypes (Leave Allocation, Salary Slip, etc.),
    if no employee or employee_name filter is given, auto-scope to
    the current user's employee.
    This handles "show my leave balance" queries.
    """
    if doctype not in _EMPLOYEE_SCOPED_DOCTYPES:
        return filters

    # Already has an employee filter — don't override
    if "employee" in filters or "employee_name" in filters:
        return filters

    employee = _get_current_employee()
    if employee and employee.get("name") and meta.get_field("employee"):
        filters = dict(filters)
        filters["employee"] = employee["name"]

    return filters


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
    """Get a single record by name or employee_name lookup."""
    doctype = str(params.get("doctype", "")).strip()
    name = str(params.get("name", "")).strip()
    if not doctype or not name:
        return []
    if not validate_doctype_in_hrms(doctype):
        return [_error_item(f"get:{doctype}", f"'{doctype}' not in HRMS modules.")]

    # If the name doesn't exist, try fuzzy employee lookup by employee_name
    if not frappe.db.exists(doctype, name):
        resolved = _resolve_by_name(doctype, name)
        if resolved:
            name = resolved
        else:
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
    fields = _ensure_display_fields(meta, doctype, fields)
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


def _resolve_by_name(doctype: str, query: str) -> str | None:
    """Try to resolve a human name to an actual document name/ID.
    Works for Employee (employee_name), Job Applicant (applicant_name), etc."""
    name_fields = {
        "Employee": "employee_name",
        "Job Applicant": "applicant_name",
        "Job Opening": "job_title",
    }
    name_field = name_fields.get(doctype)
    if not name_field:
        return None

    # Try exact match first
    result = frappe.db.get_value(doctype, {name_field: query}, "name")
    if result:
        return result

    # Try case-insensitive like match
    result = frappe.db.get_value(
        doctype, {name_field: ["like", f"%{query}%"]}, "name"
    )
    return result


# ─── Agentic Action Tool ─────────────────────────────────────────────────────

def _tool_prepare_action(params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Prepare (but don't execute) an HRMS action — create, update, submit.

    Returns validation results and a preview of the action for user confirmation.
    The actual execution happens via the confirm_action API endpoint.
    """
    action_type = str(params.get("action_type", "create")).strip()
    doctype = str(params.get("doctype", "")).strip()
    values = params.get("values") or {}

    if not doctype:
        return [_error_item("prepare_action", "DocType is required.")]
    if not validate_doctype_in_hrms(doctype):
        return [_error_item("prepare_action", f"'{doctype}' is not an HRMS DocType.")]
    if not frappe.db.exists("DocType", doctype):
        return [_error_item("prepare_action", f"DocType '{doctype}' does not exist.")]

    # Permission check
    perm_type = "create" if action_type == "create" else "write"
    if not frappe.has_permission(doctype, perm_type):
        return [
            _error_item(
                "prepare_action",
                f"You don't have {perm_type} permission for {doctype}.",
            )
        ]

    meta = frappe.get_meta(doctype)

    # Auto-fill smart defaults
    enriched_values = _enrich_defaults(meta, doctype, values)

    # Validate required fields
    missing_fields = _check_required_fields(meta, enriched_values)

    # Validate field values against meta
    validation_errors = _validate_field_values(meta, enriched_values)

    # Build preview
    preview_fields = {}
    for field_name, val in enriched_values.items():
        field_meta = meta.get_field(field_name)
        label = field_meta.label if field_meta else field_name
        preview_fields[label] = val

    return [
        {
            "source_id": f"action:prepare:{doctype}",
            "type": "action_preview",
            "action": {
                "action_type": action_type,
                "doctype": doctype,
                "values": enriched_values,
                "preview": f"Ready to {action_type} {doctype}" if not missing_fields else
                    f"Missing required fields: {', '.join(missing_fields)}",
            },
            "preview_fields": preview_fields,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "is_valid": len(missing_fields) == 0 and len(validation_errors) == 0,
        }
    ]


def _enrich_defaults(meta, doctype: str, values: dict[str, Any]) -> dict[str, Any]:
    """
    Auto-fill smart defaults based on DocType and current user context.
    Zero hardcoding — all defaults come from the user's Frappe context.
    """
    enriched = dict(values)

    # Auto-detect current user's employee
    user = frappe.session.user
    employee = _get_current_employee()

    # Employee-linked fields
    if employee:
        if "employee" in _get_field_names(meta) and "employee" not in enriched:
            enriched["employee"] = employee.get("name", "")
        if "employee_name" in _get_field_names(meta) and "employee_name" not in enriched:
            enriched["employee_name"] = employee.get("employee_name", "")
        if "company" in _get_field_names(meta) and "company" not in enriched:
            enriched["company"] = employee.get("company", "")
        if "department" in _get_field_names(meta) and "department" not in enriched:
            enriched["department"] = employee.get("department", "")

    # Date defaults
    date_fields_defaults = {
        "posting_date": today(),
        "from_date": today(),
        "transaction_date": today(),
    }
    for fname, default_val in date_fields_defaults.items():
        if fname in _get_field_names(meta) and fname not in enriched:
            enriched[fname] = default_val

    return enriched


def _get_current_employee() -> dict[str, Any] | None:
    """Look up the Employee record linked to the current session user."""
    user = frappe.session.user
    cache_key = f"ai_hrms:employee:{user}"
    cached = frappe.cache.get_value(cache_key)
    if cached:
        return cached

    emp_name = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not emp_name:
        return None

    emp = frappe.db.get_value(
        "Employee",
        emp_name,
        ["name", "employee_name", "company", "department", "designation"],
        as_dict=True,
    )
    if emp:
        frappe.cache.set_value(cache_key, emp, expires_in_sec=300)
    return emp


def _get_field_names(meta) -> set[str]:
    """Get all field names from DocType meta."""
    return {f.fieldname for f in meta.fields if f.fieldname}


_AUTO_FILLED_FIELDS = frozenset({
    "naming_series", "amended_from", "status", "docstatus",
    "owner", "modified_by", "creation", "modified",
})


def _check_required_fields(meta, values: dict[str, Any]) -> list[str]:
    """Check which required fields are missing from values.
    Skips auto-filled fields (naming_series, status with defaults, etc.)."""
    missing = []
    for f in meta.fields:
        if not f.reqd:
            continue
        if f.fieldtype in {"Section Break", "Column Break", "Tab Break", "Table"}:
            continue
        if f.fieldname in _AUTO_FILLED_FIELDS:
            continue
        # Skip fields that have a default value set
        if f.default:
            continue
        if f.fieldname not in values or not values[f.fieldname]:
            missing.append(f.label or f.fieldname)
    return missing


def _validate_field_values(meta, values: dict[str, Any]) -> list[str]:
    """Validate field values against meta (types, Link existence, etc.)."""
    errors = []
    for field_name, val in values.items():
        field = meta.get_field(field_name)
        if not field:
            continue
        # Validate Link fields — does the target record exist?
        if field.fieldtype == "Link" and val:
            if not frappe.db.exists(field.options, val):
                errors.append(
                    f"{field.label or field_name}: '{val}' not found in {field.options}"
                )
        # Validate Select fields — is the value in options?
        if field.fieldtype == "Select" and val and field.options:
            valid_options = [o.strip() for o in field.options.split("\n") if o.strip()]
            if val not in valid_options:
                errors.append(
                    f"{field.label or field_name}: '{val}' is not a valid option. "
                    f"Valid: {', '.join(valid_options[:8])}"
                )
    return errors


# ─── Registry ────────────────────────────────────────────────────────────────

_TOOL_REGISTRY: dict[str, Callable] = {
    "search_meta": _tool_search_meta,
    "list_records": _tool_list_records,
    "count_records": _tool_count_records,
    "get_record": _tool_get_record,
    "prepare_action": _tool_prepare_action,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tokenize(query: str) -> list[str]:
    """Split query into searchable tokens (unique, length > 2, max 6)."""
    tokens = [t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 2]
    return list(dict.fromkeys(tokens))[:6]


def _error_item(source_id: str, error: str) -> dict[str, Any]:
    return {"source_id": f"error:{source_id}", "type": "error", "error": error}
