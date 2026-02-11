"""
Central config accessor for AI HRMS Suite.

Reads all settings from the 'AI HRMS Settings' Single DocType.
Redis-cached for 5 min to avoid DB hits on every LLM call.
"""

import frappe

_SETTINGS_CACHE_KEY = "ai_hrms_suite:settings_dict"
_POLICIES_CACHE_KEY = "ai_hrms_suite:policies_dict"
_CACHE_TTL = 300  # 5 minutes


def _get_settings_doc():
    """Return the raw Single doc dict (cached)."""
    cached = frappe.cache.get_value(_SETTINGS_CACHE_KEY)
    if cached:
        return cached

    if not frappe.db.exists("DocType", "AI HRMS Settings"):
        return {}

    try:
        doc = frappe.get_single("AI HRMS Settings")
        data = doc.as_dict()
        frappe.cache.set_value(_SETTINGS_CACHE_KEY, data, expires_in_sec=_CACHE_TTL)
        return data
    except Exception:
        return {}


def get_conf(key: str, default=None):
    """
    Read a config value from AI HRMS Settings DocType.

    The key should be the *fieldname* in the DocType (e.g. 'enable_cache',
    'budget_usd_per_day', 'max_resume_chars').

    For backward compat, also accepts old-style prefixed keys
    (e.g. 'ai_hrms_enable_cache') — the prefix is stripped automatically.
    """
    settings = _get_settings_doc()
    if not settings:
        return default

    # Try exact fieldname first
    val = settings.get(key)
    if val is not None:
        return val

    # Strip legacy prefix: ai_hrms_ -> fieldname
    stripped = key
    if key.startswith("ai_hrms_"):
        stripped = key[len("ai_hrms_"):]
    val = settings.get(stripped)
    if val is not None:
        return val

    return default


def get_policies() -> dict:
    """
    Build the task -> [{provider, model}] policy dict from the child table.

    Returns format compatible with AIRouter:
        {
            "resume_parse": [{"provider": "openrouter", "model": "openai/gpt-4o-mini"}],
            "intent_analysis": [...],
            ...
        }
    """
    cached = frappe.cache.get_value(_POLICIES_CACHE_KEY)
    if cached:
        return cached

    settings = _get_settings_doc()
    if not settings:
        return {}

    policies: dict[str, list[dict]] = {}
    rows = settings.get("model_policies") or []
    for row in rows:
        task = row.get("task_name") if isinstance(row, dict) else getattr(row, "task_name", None)
        provider = row.get("provider") if isinstance(row, dict) else getattr(row, "provider", None)
        model = row.get("model") if isinstance(row, dict) else getattr(row, "model", None)
        priority = row.get("priority", 1) if isinstance(row, dict) else getattr(row, "priority", 1)
        if task and provider and model:
            policies.setdefault(task, []).append({
                "provider": provider,
                "model": model,
                "_priority": int(priority or 1),
            })

    # Sort each task's tiers by priority (lower = tried first)
    for task in policies:
        policies[task].sort(key=lambda t: t["_priority"])
        # Remove internal _priority key
        for tier in policies[task]:
            tier.pop("_priority", None)

    if policies:
        frappe.cache.set_value(_POLICIES_CACHE_KEY, policies, expires_in_sec=_CACHE_TTL)
    return policies


def get_api_key(provider: str) -> str:
    """Get the API key for a provider from settings (Password field)."""
    settings = _get_settings_doc()
    if not settings:
        return ""

    key_map = {
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "gemini": "gemini_api_key",
        "openrouter": "openrouter_api_key",
    }
    fieldname = key_map.get(provider, "")
    if not fieldname:
        return ""

    # Password fields need get_password()
    try:
        doc = frappe.get_single("AI HRMS Settings")
        return doc.get_password(fieldname) or ""
    except Exception:
        return ""


def get_provider_config(provider: str) -> dict:
    """Get all config keys relevant to a specific provider."""
    settings = _get_settings_doc()
    if not settings:
        return {}

    if provider == "openrouter":
        return {
            "api_key": get_api_key("openrouter"),
            "base_url": settings.get("openrouter_base_url") or "https://openrouter.ai/api/v1",
            "site_url": settings.get("openrouter_site_url") or "",
            "app_name": settings.get("openrouter_app_name") or "AI HRMS Suite",
        }
    elif provider == "openai":
        return {
            "api_key": get_api_key("openai"),
            "base_url": settings.get("openai_base_url") or "https://api.openai.com/v1",
        }
    elif provider == "anthropic":
        return {
            "api_key": get_api_key("anthropic"),
            "base_url": settings.get("anthropic_base_url") or "https://api.anthropic.com",
            "version": settings.get("anthropic_version") or "2023-06-01",
            "max_tokens": int(settings.get("anthropic_max_tokens") or 1200),
        }
    elif provider == "gemini":
        return {
            "api_key": get_api_key("gemini"),
            "base_url": settings.get("gemini_base_url") or "https://generativelanguage.googleapis.com",
        }
    return {}


def clear_settings_cache():
    """Call after saving AI HRMS Settings to bust caches."""
    frappe.cache.delete_value(_SETTINGS_CACHE_KEY)
    frappe.cache.delete_value(_POLICIES_CACHE_KEY)
