import json
import frappe
from ai_hrms_suite.ai.providers.registry import get_provider
from ai_hrms_suite.utils.validation import validate_json
from ai_hrms_suite.utils.config import get_policies, get_conf
from ai_hrms_suite.utils.budget import assert_within_budget
from ai_hrms_suite.utils.hashing import sha256_text


class AIRouter:
    """
    Cost-optimized multi-provider router:
    - Uses policy tiers from site_config (provider+model list per task)
    - Validates JSON + schema
    - Falls back to next tier on JSON/schema failure
    - Optional cache using input_hash -> output_json
    """

    def __init__(self):
        self.policies = get_policies()
        self.enable_cache = bool(get_conf("ai_hrms_enable_cache", True))
        self.max_chars = int(get_conf("ai_hrms_max_resume_chars", 20000))
        self.max_prompt_tokens = int(get_conf("ai_hrms_max_prompt_tokens", 6000))

    def run_json_task(self, task_name: str, prompt: str, schema: dict, timeout_s: int = 60):
        prompt = (prompt or "")[: self.max_chars]
        tiers = self.policies.get(task_name) or []
        if not tiers:
            raise ValueError(f"No policy tiers configured for task: {task_name}")

        input_hash = sha256_text(f"{task_name}||{prompt}")

        # 1) cache
        if self.enable_cache:
            cached = self._cache_get(task_name, input_hash)
            if cached:
                data = json.loads(cached)
                validate_json(data, schema)
                return {
                    "data": data,
                    "llm_result": None,
                    "cache_hit": True,
                    "provider": "cache",
                    "model": "cache"
                }

        # 2) try tiers
        last_err = None
        for tier in tiers:
            provider_name = tier.get("provider")
            model = tier.get("model")
            try:
                provider = get_provider(provider_name)

                # budget check before running (best-effort; cost may still be unknown)
                assert_within_budget(extra_cost_usd=0.0)

                llm_result = provider.complete_json(prompt=prompt, json_schema=schema, model=model, timeout_s=timeout_s)

                # Parse JSON
                text = (llm_result.text or "").strip()
                data = json.loads(text)

                # Validate schema
                validate_json(data, schema)

                # Cache success
                if self.enable_cache:
                    self._cache_set(task_name, input_hash, json.dumps(data, ensure_ascii=False))

                return {
                    "data": data,
                    "llm_result": llm_result,
                    "cache_hit": False,
                    "provider": provider_name,
                    "model": model
                }

            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"All tiers failed for task '{task_name}'. Last error: {str(last_err)}")

    # ---------- cache db helpers ----------

    def _cache_get(self, task_name: str, input_hash: str):
        row = frappe.get_all(
            "AI Cache",
            filters={"task_name": task_name, "input_hash": input_hash},
            fields=["output_json"],
            limit=1
        )
        if row:
            return row[0]["output_json"]
        return None

    def _cache_set(self, task_name: str, input_hash: str, output_json: str):
        existing = frappe.get_all("AI Cache", filters={"task_name": task_name, "input_hash": input_hash}, pluck="name")
        if existing:
            doc = frappe.get_doc("AI Cache", existing[0])
            doc.output_json = output_json
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.new_doc("AI Cache")
            doc.task_name = task_name
            doc.input_hash = input_hash
            doc.output_json = output_json
            doc.save(ignore_permissions=True)
