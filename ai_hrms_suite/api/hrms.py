import json
import frappe
from ai_hrms_suite.ai.pipeline import enqueue_parse_for_applicant, enqueue_rescore_for_job_opening
from ai_hrms_suite.utils.availability import get_slot_suggestions


def _get_resume_url(doc) -> str | None:
    return getattr(doc, "resume", None) or getattr(doc, "resume_attachment", None)


def on_job_applicant_updated(doc, method=None):
    resume_url = _get_resume_url(doc)
    if not resume_url:
        return

    doc_before = doc.get_doc_before_save()
    if doc_before:
        before_url = _get_resume_url(doc_before)
        if before_url == resume_url:
            if frappe.db.exists("AI Resume", {"source_applicant": doc.name}):
                return

    enqueue_parse_for_applicant(doc.name)


def on_job_opening_updated(doc, method=None):
    enqueue_rescore_for_job_opening(doc.name)


@frappe.whitelist()
def get_interview_slot_suggestions(job_opening=None, interviewers=None, days=None, slot_minutes=None, limit=None):
    if isinstance(interviewers, str):
        try:
            interviewers = json.loads(interviewers)
        except Exception:
            interviewers = [i.strip() for i in interviewers.split(",") if i.strip()]
    interviewers = interviewers or []

    suggestions = get_slot_suggestions(
        interviewers=interviewers,
        job_opening=job_opening,
        days=days,
        slot_minutes=slot_minutes,
        limit=limit,
    )

    return [s.__dict__ for s in suggestions]
