from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    raw_response: Optional[dict] = None  # for debugging if needed


class LLMProvider:
    name: str
    def complete_json(self, prompt: str, json_schema: Dict[str, Any], model: str, timeout_s: int = 60) -> LLMResult:
        raise NotImplementedError
