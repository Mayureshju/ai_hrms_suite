import frappe


def _normalize_gap(text: str) -> str:
    return " ".join((text or "").strip().split())


def execute(filters=None):
    filters = filters or {}
    job_opening = filters.get("job_opening")
    min_score = float(filters.get("min_score") or 0)
    days = int(filters.get("days") or 90)

    conditions = ["sc.match_score >= %(min_score)s"]
    if job_opening:
        conditions.append("sc.job_opening = %(job_opening)s")
    if days > 0:
        conditions.append("sc.creation >= DATE_SUB(NOW(), INTERVAL %(days)s DAY)")

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT sc.job_opening, sc.match_score, sc.gaps, sc.creation
        FROM `tabAI Screening Scorecard` sc
        WHERE {where_clause}
        """,
        {
            "job_opening": job_opening,
            "min_score": min_score,
            "days": days,
        },
        as_dict=True,
    )

    agg = {}
    for row in rows:
        gaps_text = row.get("gaps") or ""
        gaps = [g for g in gaps_text.split("\n") if g.strip()]
        for gap in gaps:
            key = (row.get("job_opening"), _normalize_gap(gap))
            if not key[1]:
                continue
            if key not in agg:
                agg[key] = {
                    "job_opening": key[0],
                    "gap": key[1],
                    "count": 0,
                    "total_score": 0.0,
                    "last_scored_on": row.get("creation"),
                }
            agg[key]["count"] += 1
            agg[key]["total_score"] += float(row.get("match_score") or 0)
            if row.get("creation") and row.get("creation") > agg[key]["last_scored_on"]:
                agg[key]["last_scored_on"] = row.get("creation")

    data = []
    for value in agg.values():
        avg_score = (value["total_score"] / value["count"]) if value["count"] else 0
        data.append(
            {
                "job_opening": value["job_opening"],
                "gap": value["gap"],
                "count": value["count"],
                "avg_match_score": round(avg_score, 2),
                "last_scored_on": value["last_scored_on"],
            }
        )

    data.sort(key=lambda d: (-d["count"], -d["avg_match_score"], d["gap"]))
    chart = _get_chart_data(data)

    columns = [
        {"label": "Job Opening", "fieldname": "job_opening", "fieldtype": "Link", "options": "Job Opening", "width": 180},
        {"label": "Gap", "fieldname": "gap", "fieldtype": "Data", "width": 260},
        {"label": "Count", "fieldname": "count", "fieldtype": "Int", "width": 80},
        {"label": "Avg Match Score", "fieldname": "avg_match_score", "fieldtype": "Float", "width": 120},
        {"label": "Last Scored On", "fieldname": "last_scored_on", "fieldtype": "Datetime", "width": 160},
    ]

    return columns, data, None, chart


def _get_chart_data(data):
    top = data[:10]
    labels = [row["gap"] for row in top]
    values = [row["count"] for row in top]
    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Gap Frequency", "values": values}],
        },
        "type": "bar",
        "fieldtype": "Int",
    }
