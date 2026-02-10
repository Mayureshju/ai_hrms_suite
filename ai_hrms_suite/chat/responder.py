"""
Node 3: Response Generation — smart model, context synthesis.

Only called when tool results need synthesis (i.e. short-circuit didn't fire).
Uses the expensive policy tier (e.g. Claude 3.5 Sonnet) for high-quality answers.
"""

import json
from typing import Any

from ai_hrms_suite.ai.router import AIRouter
from ai_hrms_suite.chat import render_chat_prompt
from ai_hrms_suite.chat.schemas import RESPONSE_SCHEMA
from ai_hrms_suite.utils.validation import validate_json


def generate_response(
    question: str,
    intent: dict[str, Any],
    tool_results: list[dict[str, Any]],
    recent_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Synthesize a final answer from tool results using a smart model.

    Returns:
        {
            "data": <parsed RESPONSE_SCHEMA dict>,
            "llm_result": <LLMResult | None>,
            "cache_hit": bool,
        }
    """
    prompt = render_chat_prompt(
        "response_v1.j2",
        schema_json=json.dumps(RESPONSE_SCHEMA, ensure_ascii=True),
        question=question,
        intent_json=json.dumps(intent, ensure_ascii=True),
        context_json=json.dumps(tool_results, ensure_ascii=True),
        recent_messages=json.dumps(recent_messages[-6:], ensure_ascii=True),
    )

    router = AIRouter()
    out = router.run_json_task(
        "response_gen",
        prompt=prompt,
        schema=RESPONSE_SCHEMA,
        timeout_s=60,
    )
    validate_json(out["data"], RESPONSE_SCHEMA)

    return {
        "data": out["data"],
        "llm_result": out["llm_result"],
        "cache_hit": out["cache_hit"],
    }
