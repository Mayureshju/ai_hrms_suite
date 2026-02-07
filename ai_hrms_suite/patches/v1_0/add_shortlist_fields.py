import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    job_applicant_fields = [
        {
            "fieldname": "ai_shortlisted",
            "label": "AI Shortlisted",
            "fieldtype": "Check",
            "default": 0,
            "in_list_view": 1,
            "read_only": 1,
            "insert_after": "status",
        },
        {
            "fieldname": "ai_match_score",
            "label": "AI Match Score",
            "fieldtype": "Float",
            "read_only": 1,
            "in_list_view": 1,
            "insert_after": "ai_shortlisted",
        },
        {
            "fieldname": "ai_shortlisted_on",
            "label": "AI Shortlisted On",
            "fieldtype": "Datetime",
            "read_only": 1,
            "insert_after": "ai_match_score",
        },
        {
            "fieldname": "ai_shortlist_notified",
            "label": "AI Shortlist Notified",
            "fieldtype": "Check",
            "default": 0,
            "read_only": 1,
            "insert_after": "ai_shortlisted_on",
        },
    ]

    job_opening_fields = [
        {
            "fieldname": "ai_shortlist_enabled",
            "label": "AI Shortlist Enabled",
            "fieldtype": "Check",
            "default": 1,
            "insert_after": "status",
        },
        {
            "fieldname": "ai_shortlist_threshold",
            "label": "AI Shortlist Threshold",
            "fieldtype": "Float",
            "default": 70,
            "insert_after": "ai_shortlist_enabled",
        },
    ]

    create_custom_fields(
        {
            "Job Applicant": job_applicant_fields,
            "Job Opening": job_opening_fields,
        },
        update=True,
    )

    frappe.clear_cache()
