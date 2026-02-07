import frappe
from ai_hrms_suite.utils.config import get_conf


def get_shortlist_threshold(job_opening_id: str | None = None) -> float | None:
    if job_opening_id and frappe.db.exists("Job Opening", job_opening_id):
        job = frappe.get_doc("Job Opening", job_opening_id)
        if hasattr(job, "ai_shortlist_enabled") and not int(job.get("ai_shortlist_enabled") or 0):
            return None
        if hasattr(job, "ai_shortlist_threshold") and job.get("ai_shortlist_threshold") is not None:
            return float(job.get("ai_shortlist_threshold"))
    return float(get_conf("ai_hrms_shortlist_threshold", 70))


def should_shortlist(match_score: float, threshold: float | None) -> bool:
    if threshold is None:
        return False
    return float(match_score) >= float(threshold)


def get_shortlist_email_recipients(applicant_doc) -> list[str]:
    configured = get_conf("ai_hrms_shortlist_email_recipients", []) or []
    if isinstance(configured, str):
        configured = [c.strip() for c in configured.split(",") if c.strip()]
    if configured:
        return configured
    email = getattr(applicant_doc, "email_id", None)
    return [email] if email else []
