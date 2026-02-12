"""
HRMS-scoped DocType metadata and record retrieval utilities.

All queries are scoped to modules belonging to the hrms / ai_hrms_suite apps.
Module lists and domain maps are cached in Redis (1 h TTL) to avoid repeated DB hits.
"""

import json
from typing import Any

import frappe


# ─── Constants ────────────────────────────────────────────────────────────────

_MODULE_CACHE_KEY = "ai_hrms_suite:hrms_modules"
_DOMAIN_MAP_CACHE_KEY = "ai_hrms_suite:domain_map"
_HRMS_DOCTYPES_CACHE_KEY = "ai_hrms_suite:hrms_doctypes"

_SKIP_FIELD_TYPES = frozenset(
    {
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Button",
        "Table",
        "Fold",
        "Heading",
    }
)

# HR-essential DocTypes that live in erpnext modules (Setup, etc.)
# but are core to HRMS operations — always included in the HRMS scope.
_EXTRA_HRMS_DOCTYPES = frozenset({
    # Core employee
    "Employee",
    "Employee Group",
    "Employee Separation",
    "Employee Onboarding",
    # Org structure
    "Holiday List",
    "Department",
    "Designation",
    "Branch",
    "Employment Type",
    "Company",
    # Leave management (critical for leave balance queries)
    "Leave Allocation",
    "Leave Application",
    "Leave Type",
    "Leave Ledger Entry",
    "Leave Encashment",
    "Leave Policy",
    "Leave Policy Assignment",
    "Leave Period",
    "Compensatory Leave Request",
    # Attendance
    "Attendance",
    "Attendance Request",
    # Payroll
    "Salary Slip",
    "Salary Structure",
    "Salary Structure Assignment",
    "Payroll Entry",
    # Expense
    "Expense Claim",
    "Expense Claim Type",
})


# ─── Module / Domain Map ─────────────────────────────────────────────────────

def get_hrms_modules() -> list[str]:
    """Return module names for hrms + ai_hrms_suite apps (cached 1 h)."""
    cached = frappe.cache.get_value(_MODULE_CACHE_KEY)
    if cached:
        return cached
    modules = frappe.get_all(
        "Module Def",
        filters={"app_name": ["in", ["hrms", "ai_hrms_suite"]]},
        pluck="name",
    )
    if modules:
        frappe.cache.set_value(_MODULE_CACHE_KEY, modules, expires_in_sec=3600)
    return modules


def get_hrms_domain_map() -> dict[str, list[str]]:
    """Build module → doctype-list map from HRMS modules (cached 1 h).
    Also includes essential HR DocTypes from erpnext under an 'HR Core' group."""
    cached = frappe.cache.get_value(_DOMAIN_MAP_CACHE_KEY)
    if cached:
        return cached
    modules = get_hrms_modules()
    domain_map: dict[str, list[str]] = {}
    for module in modules:
        doctypes = frappe.get_all(
            "DocType",
            filters={"module": module, "istable": 0, "custom": 0},
            pluck="name",
            limit=50,
        )
        if doctypes:
            domain_map[module] = doctypes
    # Add essential HR DocTypes that live outside the hrms app
    extra_found = [dt for dt in _EXTRA_HRMS_DOCTYPES if frappe.db.exists("DocType", dt)]
    if extra_found:
        domain_map["HR Core (ERPNext)"] = sorted(extra_found)
    if domain_map:
        frappe.cache.set_value(_DOMAIN_MAP_CACHE_KEY, domain_map, expires_in_sec=3600)
    return domain_map


def get_all_hrms_doctypes() -> set[str]:
    """Flat set of all non-table doctype names in HRMS modules (cached 1 h).
    Also includes essential HR DocTypes from erpnext (Employee, Department, etc.)."""
    cached = frappe.cache.get_value(_HRMS_DOCTYPES_CACHE_KEY)
    if cached:
        return set(cached)
    domain_map = get_hrms_domain_map()
    result: set[str] = set()
    for doctypes in domain_map.values():
        result.update(doctypes)
    # Add HR-essential DocTypes from erpnext
    result.update(_EXTRA_HRMS_DOCTYPES)
    if result:
        frappe.cache.set_value(
            _HRMS_DOCTYPES_CACHE_KEY, list(result), expires_in_sec=3600
        )
    return result


def validate_doctype_in_hrms(doctype: str) -> bool:
    """Check if a doctype belongs to an HRMS module."""
    return doctype in get_all_hrms_doctypes()


def build_domain_map_payload() -> str:
    """
    Compact JSON payload of the domain map for the intent prompt.
    
    Includes:
    - domain_map: module → doctype-list mapping
    - agentic_enabled: whether agentic (write) mode is enabled
    
    The agentic_enabled flag helps the LLM avoid planning actions
    when they will be blocked by settings.
    """
    from ai_hrms_suite.utils.config import is_agentic_enabled
    
    payload = {
        "domain_map": get_hrms_domain_map(),
        "agentic_enabled": is_agentic_enabled(),
    }
    return json.dumps(payload, ensure_ascii=True)


# ─── Field helpers ────────────────────────────────────────────────────────────

def safe_field_summary(meta, max_fields: int = 12) -> list[dict[str, Any]]:
    """Extract non-hidden, non-layout field summary from DocType meta."""
    fields: list[dict[str, Any]] = []
    for f in meta.fields or []:
        if f.fieldtype in _SKIP_FIELD_TYPES or f.hidden:
            continue
        fields.append(
            {
                "label": f.label or f.fieldname,
                "fieldname": f.fieldname,
                "fieldtype": f.fieldtype,
                "options": f.options if f.fieldtype in {"Link", "Select"} else "",
            }
        )
        if len(fields) >= max_fields:
            break
    return fields


def truncate_value(value: Any, limit: int = 240) -> Any:
    """Truncate long string values for safe inclusion in LLM context."""
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


# ─── Filter / field sanitization ─────────────────────────────────────────────

_SAFE_FILTER_TYPES = frozenset(
    {"Link", "Select", "Data", "Int", "Float", "Date", "Datetime"}
)

# Operators we allow in ["operator", "value"] style filters
_SAFE_FILTER_OPS = frozenset(
    {"=", "!=", ">", "<", ">=", "<=", "like", "not like", "in", "not in", "is"}
)


def allowed_filter_field(meta, fieldname: str) -> bool:
    """Return True if fieldname is safe to use in filters."""
    if fieldname == "name":
        return True
    field = meta.get_field(fieldname)
    if not field:
        return False
    return field.fieldtype in _SAFE_FILTER_TYPES


def sanitize_filters(meta, filters: dict[str, Any]) -> dict[str, Any]:
    """Strip filters to only allowed field names & scalar values.

    Supports both simple scalar filters {"field": "value"}
    and operator filters {"field": ["like", "%value%"]}.
    """
    out: dict[str, Any] = {}
    for key, value in (filters or {}).items():
        if not isinstance(key, str):
            continue
        if not allowed_filter_field(meta, key):
            continue
        # Simple scalar value
        if isinstance(value, (str, int, float)):
            out[key] = value
        # Operator-style filter: ["like", "%name%"]
        elif isinstance(value, list) and len(value) == 2:
            op = str(value[0]).lower().strip()
            operand = value[1]
            if op in _SAFE_FILTER_OPS and isinstance(operand, (str, int, float)):
                out[key] = [op, operand]
    return out


def sanitize_fields(meta, fields: list[str]) -> list[str]:
    """Validate requested fields exist in meta; cap at 8."""
    if not fields:
        return ["name"]
    allowed: list[str] = []
    for f in fields:
        if not isinstance(f, str):
            continue
        if allowed_filter_field(meta, f) or meta.get_field(f):
            allowed.append(f)
    return allowed[:8] or ["name"]
