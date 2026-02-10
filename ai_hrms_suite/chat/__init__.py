"""HRMS Chatbot — Hybrid 3-node pipeline for cost-optimized, accurate HRMS Q&A."""

import os

import frappe
from jinja2 import Template


def render_chat_prompt(template_name: str, **kwargs) -> str:
    """Render a Jinja2 template from the chat/prompts directory."""
    path = os.path.join(
        frappe.get_app_path("ai_hrms_suite"), "chat", "prompts", template_name
    )
    with open(path, "r", encoding="utf-8") as f:
        return Template(f.read()).render(**kwargs)
