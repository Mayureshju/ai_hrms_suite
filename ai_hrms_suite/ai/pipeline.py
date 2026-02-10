import os
import json
import frappe
from jinja2 import Template

from ai_hrms_suite.ai.schemas import RESUME_PARSE_SCHEMA, JD_MATCH_SCHEMA
from ai_hrms_suite.ai.router import AIRouter
from ai_hrms_suite.extractors.pdf_text import extract_pdf_text
from ai_hrms_suite.extractors.docx_text import extract_docx_text
from ai_hrms_suite.utils.hashing import sha256_text
from ai_hrms_suite.utils.shortlist import (
    get_shortlist_threshold,
    should_shortlist,
    get_shortlist_email_recipients,
)
from ai_hrms_suite.utils.config import get_conf


def enqueue_parse_for_applicant(applicant_id: str):
    applicant = frappe.get_doc("Job Applicant", applicant_id)

    # Try common resume fields (adjust if your instance uses a custom field)
    file_url = getattr(applicant, "resume", None) or getattr(applicant, "resume_attachment", None)
    if not file_url:
        return

    frappe.enqueue(
        "ai_hrms_suite.ai.pipeline.parse_resume_for_applicant",
        queue="long",
        applicant_id=applicant_id,
        job_name=f"ai_parse_resume::{applicant_id}",
        enqueue_after_commit=True
    )


def enqueue_rescore_for_job_opening(job_opening_id: str):
    frappe.enqueue(
        "ai_hrms_suite.ai.pipeline.rescore_job_opening",
        queue="long",
        job_opening_id=job_opening_id,
        job_name=f"ai_rescore_job::{job_opening_id}",
        enqueue_after_commit=True
    )


def _render_prompt(template_name: str, **kwargs) -> str:
    from frappe import get_app_path
    path = os.path.join(get_app_path("ai_hrms_suite"), "ai", "prompts", template_name)
    with open(path, "r", encoding="utf-8") as f:
        return Template(f.read()).render(**kwargs)


def parse_resume_for_applicant(applicant_id: str):
    if not frappe.db.exists("Job Applicant", applicant_id):
        return
    applicant = frappe.get_doc("Job Applicant", applicant_id)
    file_url = getattr(applicant, "resume", None) or getattr(applicant, "resume_attachment", None)
    if not file_url:
        return

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = file_doc.get_full_path()
    filename = (file_doc.file_name or "").lower()

    if filename.endswith(".pdf"):
        resume_text = extract_pdf_text(file_path)
    elif filename.endswith(".docx"):
        resume_text = extract_docx_text(file_path)
    else:
        raise ValueError(f"Unsupported resume format: {file_doc.file_name}")

    store_raw = bool(get_conf("store_raw_text", False))

    extracted_hash = sha256_text(resume_text)

    prompt = _render_prompt(
        "resume_parse_v1.j2",
        schema_json=json.dumps(RESUME_PARSE_SCHEMA),
        resume_text=resume_text[: int(get_conf("max_resume_chars", 20000))]
    )

    router = AIRouter()
    out = router.run_json_task("resume_parse", prompt=prompt, schema=RESUME_PARSE_SCHEMA, timeout_s=60)
    parsed = out["data"]
    llm_result = out["llm_result"]

    ai_resume_name = _upsert_ai_resume(applicant_id, file_doc.name, extracted_hash, status="Done")
    _save_parse_result(ai_resume_name, parsed, (resume_text if store_raw else ""), llm_result, cache_hit=out["cache_hit"])

    job_opening = getattr(applicant, "job_opening", None) or getattr(applicant, "job_title", None)
    if job_opening:
        frappe.enqueue(
            "ai_hrms_suite.ai.pipeline.score_applicant_for_job",
            queue="long",
            applicant_id=applicant_id,
            job_opening_id=job_opening,
            job_name=f"ai_score::{job_opening}::{applicant_id}"
        )


def score_applicant_for_job(applicant_id: str, job_opening_id: str):
    if not frappe.db.exists("Job Applicant", applicant_id):
        return
    if not frappe.db.exists("Job Opening", job_opening_id):
        return
    applicant = frappe.get_doc("Job Applicant", applicant_id)
    job = frappe.get_doc("Job Opening", job_opening_id)

    resume_json = _get_latest_resume_json(applicant_id)
    if not resume_json:
        return

    jd_text = getattr(job, "description", None) or getattr(job, "job_description", None) or ""

    prompt = _render_prompt(
        "jd_match_v1.j2",
        schema_json=json.dumps(JD_MATCH_SCHEMA),
        jd_text=jd_text[: int(get_conf("max_resume_chars", 20000))],
        resume_json=json.dumps(resume_json, ensure_ascii=False)[: int(get_conf("max_resume_chars", 20000))]
    )

    router = AIRouter()
    out = router.run_json_task("jd_match", prompt=prompt, schema=JD_MATCH_SCHEMA, timeout_s=60)
    scored = out["data"]
    llm_result = out["llm_result"]

    _save_scorecard(applicant_id, job_opening_id, scored, llm_result, cache_hit=out["cache_hit"])


def rescore_job_opening(job_opening_id: str):
    applicants = frappe.get_all("Job Applicant", filters={"job_opening": job_opening_id}, pluck="name")
    for a in applicants:
        frappe.enqueue(
            "ai_hrms_suite.ai.pipeline.score_applicant_for_job",
            queue="long",
            applicant_id=a,
            job_opening_id=job_opening_id,
            job_name=f"ai_score::{job_opening_id}::{a}"
        )


# ---------- Persistence helpers ----------

def _upsert_ai_resume(applicant_id: str, file_id: str, text_hash: str, status: str = "Done") -> str:
    existing = frappe.get_all("AI Resume", filters={"source_applicant": applicant_id}, pluck="name")
    if existing:
        doc = frappe.get_doc("AI Resume", existing[0])
    else:
        doc = frappe.new_doc("AI Resume")
        doc.source_applicant = applicant_id

    doc.resume_file = file_id
    doc.extracted_text_hash = text_hash
    doc.status = status
    doc.parse_version = "v1"
    doc.save(ignore_permissions=True)
    return doc.name


def _save_parse_result(ai_resume_name: str, parsed_json: dict, raw_text: str, llm_result, cache_hit: bool):
    doc = frappe.new_doc("AI Resume Parse Result")
    doc.ai_resume = ai_resume_name
    doc.structured_json = json.dumps(parsed_json, ensure_ascii=False, indent=2)
    doc.raw_text = raw_text or ""
    doc.provider = getattr(llm_result, "provider", "cache") if llm_result else "cache"
    doc.model = getattr(llm_result, "model", "cache") if llm_result else "cache"
    doc.save(ignore_permissions=True)

    _log_run("parse_resume", llm_result, status="Success", error="", cache_hit=cache_hit)


def _get_latest_resume_json(applicant_id: str):
    ai_resumes = frappe.get_all("AI Resume", filters={"source_applicant": applicant_id}, pluck="name")
    if not ai_resumes:
        return None
    latest = frappe.get_all(
        "AI Resume Parse Result",
        filters={"ai_resume": ai_resumes[0]},
        fields=["structured_json"],
        order_by="creation desc",
        limit=1
    )
    if not latest:
        return None
    return json.loads(latest[0]["structured_json"])


def _save_scorecard(applicant_id: str, job_opening_id: str, scored: dict, llm_result, cache_hit: bool):
    doc = frappe.new_doc("AI Screening Scorecard")
    doc.applicant = applicant_id
    doc.job_opening = job_opening_id
    doc.match_score = float(scored["match_score"])
    doc.strengths = "\n".join(scored.get("strengths", []))
    doc.gaps = "\n".join(scored.get("gaps", []))
    doc.risk_flags = "\n".join(scored.get("risk_flags", []))
    doc.explanation = scored.get("explanation", "")
    doc.score_version = "v1"
    doc.save(ignore_permissions=True)

    _log_run("score_resume", llm_result, status="Success", error="", cache_hit=cache_hit)

    _apply_shortlist(applicant_id, job_opening_id, doc.name, float(scored["match_score"]))


def _apply_shortlist(applicant_id: str, job_opening_id: str, scorecard_name: str, match_score: float):
    if not frappe.db.exists("Job Applicant", applicant_id):
        return

    threshold = get_shortlist_threshold(job_opening_id)
    shortlisted = should_shortlist(match_score, threshold)

    values = {
        "ai_shortlisted": 1 if shortlisted else 0,
        "ai_match_score": float(match_score),
    }
    if shortlisted:
        values["ai_shortlisted_on"] = frappe.utils.now_datetime()

    frappe.db.set_value("Job Applicant", applicant_id, values, update_modified=True)

    if not shortlisted:
        return

    _maybe_create_interview(applicant_id, job_opening_id)

    if not int(get_conf("ai_hrms_shortlist_send_email", 0) or 0):
        return

    applicant = frappe.get_doc("Job Applicant", applicant_id)
    if int(getattr(applicant, "ai_shortlist_notified", 0) or 0):
        return

    recipients = get_shortlist_email_recipients(applicant)
    if not recipients:
        return

    subject = get_conf("ai_hrms_shortlist_email_subject", "Shortlisted for interview")
    context = {
        "applicant_name": getattr(applicant, "applicant_name", ""),
        "job_title": getattr(applicant, "job_title", ""),
        "company_name": frappe.defaults.get_global_default("company") or "",
        "scorecard": scorecard_name,
        "match_score": match_score,
        "threshold": threshold,
    }
    message = frappe.render_template("ai_hrms_suite/templates/emails/ai_shortlist_candidate.html", context)
    if not frappe.db.exists("Email Account", {"enable_outgoing": 1}):
        return

    try:
        frappe.sendmail(recipients=recipients, subject=subject, message=message)
        frappe.db.set_value("Job Applicant", applicant_id, "ai_shortlist_notified", 1, update_modified=False)
    except frappe.exceptions.OutgoingEmailError:
        return


def _maybe_create_interview(applicant_id: str, job_opening_id: str):
    if not int(get_conf("ai_hrms_auto_create_interview", 0) or 0):
        return
    if not frappe.db.exists("Job Opening", job_opening_id):
        return

    job = frappe.get_doc("Job Opening", job_opening_id)
    if hasattr(job, "ai_interview_auto_create") and not int(job.get("ai_interview_auto_create") or 0):
        return

    existing = frappe.db.exists(
        "Interview",
        {"job_applicant": applicant_id, "job_opening": job_opening_id, "status": ["in", ["Pending", "Under Review"]]},
    )
    if existing:
        return

    interview_round = None
    if hasattr(job, "ai_interview_round") and job.get("ai_interview_round"):
        interview_round = job.get("ai_interview_round")
    else:
        interview_round = get_conf("ai_hrms_default_interview_round")

    if not interview_round:
        return

    offset_days = None
    if hasattr(job, "ai_interview_offset_days") and job.get("ai_interview_offset_days") is not None:
        offset_days = int(job.get("ai_interview_offset_days") or 0)
    else:
        offset_days = int(get_conf("ai_hrms_interview_offset_days", 1) or 1)

    from_time = None
    if hasattr(job, "ai_interview_from_time") and job.get("ai_interview_from_time"):
        from_time = job.get("ai_interview_from_time")
    else:
        from_time = get_conf("ai_hrms_interview_from_time")

    to_time = None
    if hasattr(job, "ai_interview_to_time") and job.get("ai_interview_to_time"):
        to_time = job.get("ai_interview_to_time")
    else:
        to_time = get_conf("ai_hrms_interview_to_time")

    if not from_time or not to_time:
        return

    scheduled_on = frappe.utils.add_days(frappe.utils.nowdate(), offset_days)

    doc = frappe.new_doc("Interview")
    doc.job_applicant = applicant_id
    doc.interview_round = interview_round
    doc.scheduled_on = scheduled_on
    doc.from_time = from_time
    doc.to_time = to_time
    doc.status = "Pending"
    doc.save(ignore_permissions=True)


def _log_run(run_type: str, llm_result, status: str, error: str = "", cache_hit: bool = False):
    log = frappe.new_doc("AI Run Log")
    log.run_type = run_type
    log.provider = getattr(llm_result, "provider", "cache") if llm_result else "cache"
    log.model = getattr(llm_result, "model", "cache") if llm_result else "cache"
    log.tokens_in = int(getattr(llm_result, "tokens_in", 0) or 0) if llm_result else 0
    log.tokens_out = int(getattr(llm_result, "tokens_out", 0) or 0) if llm_result else 0
    log.cost_usd = float(getattr(llm_result, "cost_usd", 0.0) or 0.0) if llm_result else 0.0
    log.latency_ms = int(getattr(llm_result, "latency_ms", 0) or 0) if llm_result else 0
    log.status = status
    log.error = error or ("CACHE_HIT" if cache_hit else "")
    log.save(ignore_permissions=True)
