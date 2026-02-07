import frappe


def execute(filters=None):
    filters = filters or {}
    job_opening = filters.get("job_opening")
    min_score = float(filters.get("min_score") or 0)
    limit = int(filters.get("limit") or 25)

    conditions = ["sc.match_score >= %(min_score)s"]
    if job_opening:
        conditions.append("sc.job_opening = %(job_opening)s")

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            sc.applicant AS applicant,
            ja.applicant_name AS applicant_name,
            sc.job_opening AS job_opening,
            sc.match_score AS match_score,
            sc.strengths AS strengths,
            sc.gaps AS gaps,
            sc.risk_flags AS risk_flags,
            sc.explanation AS explanation,
            sc.creation AS scored_on
        FROM `tabAI Screening Scorecard` sc
        LEFT JOIN `tabJob Applicant` ja ON ja.name = sc.applicant
        WHERE {where_clause}
        ORDER BY sc.match_score DESC, sc.creation DESC
        LIMIT %(limit)s
        """,
        {
            "job_opening": job_opening,
            "min_score": min_score,
            "limit": limit,
        },
        as_dict=True,
    )

    columns = [
        {"label": "Applicant", "fieldname": "applicant", "fieldtype": "Link", "options": "Job Applicant", "width": 160},
        {"label": "Applicant Name", "fieldname": "applicant_name", "fieldtype": "Data", "width": 180},
        {"label": "Job Opening", "fieldname": "job_opening", "fieldtype": "Link", "options": "Job Opening", "width": 180},
        {"label": "Match Score", "fieldname": "match_score", "fieldtype": "Float", "width": 110},
        {"label": "Strengths", "fieldname": "strengths", "fieldtype": "Small Text", "width": 220},
        {"label": "Gaps", "fieldname": "gaps", "fieldtype": "Small Text", "width": 220},
        {"label": "Risk Flags", "fieldname": "risk_flags", "fieldtype": "Small Text", "width": 220},
        {"label": "Explanation", "fieldname": "explanation", "fieldtype": "Small Text", "width": 260},
        {"label": "Scored On", "fieldname": "scored_on", "fieldtype": "Datetime", "width": 160},
    ]

    return columns, data
