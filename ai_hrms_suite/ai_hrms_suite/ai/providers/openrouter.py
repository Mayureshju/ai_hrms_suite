import time
import requests
import frappe
from ai_hrms_suite.ai.providers.base import LLMProvider, LLMResult


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def complete_json(self, prompt: str, json_schema, model: str, timeout_s: int = 60) -> LLMResult:
        api_key = frappe.conf.get("openrouter_api_key") or frappe.get_site_config().get("openrouter_api_key")
        if not api_key:
            raise ValueError("Missing openrouter_api_key in site_config.json")

        base_url = frappe.conf.get("openrouter_base_url") or "https://openrouter.ai/api/v1"
        site_url = frappe.conf.get("openrouter_site_url") or ""
        app_name = frappe.conf.get("openrouter_app_name") or "AI HRMS Suite"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_name:
            headers["X-Title"] = app_name

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
            raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text[:800]}")

        data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}

        # OpenRouter sometimes includes "cost" in response; if not, keep 0.
        return LLMResult(
            text=content,
            model=model,
            provider=self.name,
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
            cost_usd=float(data.get("cost") or 0.0),
            latency_ms=latency_ms,
            raw_response=data
        )
