import time
import requests
from ai_hrms_suite.ai.providers.base import LLMProvider, LLMResult
from ai_hrms_suite.utils.config import get_provider_config


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def complete_json(self, prompt: str, json_schema, model: str, timeout_s: int = 60) -> LLMResult:
        cfg = get_provider_config("anthropic")
        api_key = cfg.get("api_key")
        if not api_key:
            raise ValueError("Missing Anthropic API key in AI HRMS Settings")

        base_url = cfg.get("base_url") or "https://api.anthropic.com"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": cfg.get("version") or "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": model,
            "max_tokens": int(cfg.get("max_tokens") or 1200),
            "temperature": 0.2,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "system": "Return ONLY valid JSON. No markdown. No extra text."
        }

        t0 = time.time()
        r = requests.post(f"{base_url}/v1/messages", json=payload, headers=headers, timeout=timeout_s)
        latency_ms = int((time.time() - t0) * 1000)

        if r.status_code >= 400:
            raise RuntimeError(f"Anthropic error {r.status_code}: {r.text[:800]}")

        data = r.json()

        # Anthropic returns content blocks
        blocks = data.get("content") or []
        content = ""
        if blocks and isinstance(blocks, list) and "text" in blocks[0]:
            content = blocks[0]["text"]
        else:
            content = str(blocks)

        usage = data.get("usage") or {}
        return LLMResult(
            text=content,
            model=model,
            provider=self.name,
            tokens_in=int(usage.get("input_tokens") or 0),
            tokens_out=int(usage.get("output_tokens") or 0),
            cost_usd=0.0,
            latency_ms=latency_ms,
            raw_response=data
        )
