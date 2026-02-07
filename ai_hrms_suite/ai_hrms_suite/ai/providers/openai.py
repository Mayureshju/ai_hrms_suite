import time
import requests
import frappe
from ai_hrms_suite.ai.providers.base import LLMProvider, LLMResult


class OpenAIProvider(LLMProvider):
    name = "openai"

    def complete_json(self, prompt: str, json_schema, model: str, timeout_s: int = 60) -> LLMResult:
        api_key = frappe.conf.get("openai_api_key") or frappe.get_site_config().get("openai_api_key")
        if not api_key:
            raise ValueError("Missing openai_api_key in site_config.json")

        base_url = frappe.conf.get("openai_base_url") or "https://api.openai.com/v1"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Return ONLY valid JSON. No markdown. No extra text."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        t0 = time.time()
        r = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=timeout_s)
        latency_ms = int((time.time() - t0) * 1000)

        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI error {r.status_code}: {r.text[:800]}")

        data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}

        # OpenAI response doesn't include cost. Cost is computed elsewhere or left 0.
        return LLMResult(
            text=content,
            model=model,
            provider=self.name,
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
            cost_usd=0.0,
            latency_ms=latency_ms,
            raw_response=data
        )
