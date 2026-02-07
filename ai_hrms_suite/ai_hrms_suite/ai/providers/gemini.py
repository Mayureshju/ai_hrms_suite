import time
import requests
import frappe
from ai_hrms_suite.ai.providers.base import LLMProvider, LLMResult


class GeminiProvider(LLMProvider):
    name = "gemini"

    def complete_json(self, prompt: str, json_schema, model: str, timeout_s: int = 60) -> LLMResult:
        api_key = frappe.conf.get("gemini_api_key") or frappe.get_site_config().get("gemini_api_key")
        if not api_key:
            raise ValueError("Missing gemini_api_key in site_config.json")

        base_url = frappe.conf.get("gemini_base_url") or "https://generativelanguage.googleapis.com"
        # Google endpoint format: /v1beta/models/{model}:generateContent?key=...
        url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": "Return ONLY valid JSON. No markdown. No extra text.\n\n" + prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }

        t0 = time.time()
        r = requests.post(url, json=payload, timeout=timeout_s)
        latency_ms = int((time.time() - t0) * 1000)

        if r.status_code >= 400:
            raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:800]}")

        data = r.json()
        # Gemini response: candidates[0].content.parts[0].text
        content = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = ((candidates[0].get("content") or {}).get("parts") or [])
            if parts and "text" in parts[0]:
                content = parts[0]["text"]

        # Token usage location can vary; keep 0 if not present
        usage = data.get("usageMetadata") or {}
        return LLMResult(
            text=content,
            model=model,
            provider=self.name,
            tokens_in=int(usage.get("promptTokenCount") or 0),
            tokens_out=int(usage.get("candidatesTokenCount") or 0),
            cost_usd=0.0,
            latency_ms=latency_ms,
            raw_response=data
        )
