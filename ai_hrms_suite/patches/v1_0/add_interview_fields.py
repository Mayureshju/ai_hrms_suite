import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    job_opening_fields = [
        {
            "fieldname": "ai_interview_auto_create",
            "label": "AI Auto Create Interview",
            "fieldtype": "Check",
            "default": 0,
            "insert_after": "ai_shortlist_threshold",
        },
        {
            "fieldname": "ai_interview_round",
            "label": "AI Interview Round",
            "fieldtype": "Link",
            "options": "Interview Round",
            "insert_after": "ai_interview_auto_create",
        },
        {
            "fieldname": "ai_interview_offset_days",
            "label": "AI Interview Offset Days",
            "fieldtype": "Int",
            "default": 1,
            "insert_after": "ai_interview_round",
        },
        {
            "fieldname": "ai_interview_from_time",
            "label": "AI Interview From Time",
            "fieldtype": "Time",
            "insert_after": "ai_interview_offset_days",
        },
        {
            "fieldname": "ai_interview_to_time",
            "label": "AI Interview To Time",
            "fieldtype": "Time",
            "insert_after": "ai_interview_from_time",
        },
    ]

    create_custom_fields(
        {
            "Job Opening": job_opening_fields,
        },
        update=True,
    )

    frappe.clear_cache()
