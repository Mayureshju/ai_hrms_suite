"""
Node 1: Intent Analysis — cheap model, fast classification + tool planning.

Uses the cheapest policy tier (e.g. gpt-4o-mini) to classify the user's
question, extract entities, and plan the minimal set of tool calls needed.
"""

import json
from typing import Any

from ai_hrms_suite.ai.router import AIRouter
from ai_hrms_suite.chat import render_chat_prompt
from ai_hrms_suite.chat.schemas import INTENT_SCHEMA
from ai_hrms_suite.chat.retriever import build_domain_map_payload
from ai_hrms_suite.utils.validation import validate_json


def analyze_intent(
    question: str,
    recent_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Classify user question and produce a tool-call plan.

    Returns:
        {
            "intent": <parsed INTENT_SCHEMA dict>,
            "llm_result": <LLMResult | None>,
            "cache_hit": bool,
        }
    """
    domain_map_payload = build_domain_map_payload()

    prompt = render_chat_prompt(
        "intent_v1.j2",
        schema_json=json.dumps(INTENT_SCHEMA, ensure_ascii=True),
        question=question,
        recent_messages=json.dumps(recent_messages[-6:], ensure_ascii=True),
        domain_map=domain_map_payload,
    )

    router = AIRouter()
    out = router.run_json_task(
        "intent_analysis",
        prompt=prompt,
        schema=INTENT_SCHEMA,
        timeout_s=30,
    )
    validate_json(out["data"], INTENT_SCHEMA)

    return {
        "intent": out["data"],
        "llm_result": out["llm_result"],
        "cache_hit": out["cache_hit"],
    }
