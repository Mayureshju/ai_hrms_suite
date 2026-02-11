"""
JSON schemas for the 3-node hybrid pipeline.

Node 1 (Intent) — cheap model classifies + plans tool calls.
Node 3 (Response) — smart model synthesizes final answer from tool results.
"""

# ─── Node 1: Intent Analysis ─────────────────────────────────────────────────

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "greeting",           # hi / hello / thanks
                "question",            # any informational HRMS query
                "action_request",      # create / update / delete (agentic)
                "report_request",      # aggregate data / analytics
                "navigation",          # "where do I find X"
                "clarification",       # follow-up / disambiguation
            ],
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "domain": {
            "type": "string",
            "enum": [
                "employee",
                "leave",
                "attendance",
                "payroll",
                "recruitment",
                "expense",
                "performance",
                "shift",
                "training",
                "fleet",
                "general",
            ],
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "doctype",
                            "employee",
                            "date_range",
                            "amount",
                            "status",
                            "department",
                            "designation",
                            "leave_type",
                            "other",
                        ],
                    },
                    "value": {"type": "string"},
                    "field_hint": {"type": "string"},
                },
                "required": ["type", "value"],
                "additionalProperties": False,
            },
            "maxItems": 8,
        },
        "tools": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": [
                            "search_meta",
                            "list_records",
                            "count_records",
                            "get_record",
                            "prepare_action",
                        ],
                    },
                    "params": {"type": "object"},
                },
                "required": ["tool", "params"],
                "additionalProperties": False,
            },
            "maxItems": 4,
        },
        "short_answer": {
            "type": "string",
        },
        "reasoning": {
            "type": "string",
        },
    },
    "required": ["intent", "confidence", "domain", "tools"],
    "additionalProperties": False,
}


# ─── Node 3: Response Generation ─────────────────────────────────────────────

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["source_id"],
                "additionalProperties": False,
            },
            "maxItems": 8,
        },
        "suggested_questions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
        "action_plan": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["create", "update", "submit"],
                },
                "doctype": {"type": "string"},
                "values": {"type": "object"},
                "preview": {"type": "string"},
            },
        },
    },
    "required": ["answer", "sources", "confidence"],
    "additionalProperties": False,
}
