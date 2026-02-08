from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

import frappe
from frappe.utils import add_days, get_time, nowdate

from ai_hrms_suite.utils.config import get_conf


@dataclass
class SlotSuggestion:
    scheduled_on: str
    from_time: str
    to_time: str
    key: str
    label: str


def _to_time(value: str | time | None) -> time | None:
    if not value:
        return None
    if isinstance(value, time):
        return value
    return get_time(value)


def _build_ranges_by_interviewer(interviewers: list[str], from_date: str, to_date: str) -> dict[str, list[tuple[datetime, datetime]]]:
    if not interviewers:
        return {}

    rows = frappe.db.sql(
        """
        SELECT i.scheduled_on, i.from_time, i.to_time, d.interviewer
        FROM `tabInterview` i
        INNER JOIN `tabInterview Detail` d ON d.parent = i.name
        WHERE d.interviewer IN %(interviewers)s
          AND i.docstatus < 2
          AND i.scheduled_on BETWEEN %(from_date)s AND %(to_date)s
          AND i.status != 'Rejected'
        """,
        {"interviewers": tuple(interviewers), "from_date": from_date, "to_date": to_date},
        as_dict=True,
    )

    by_interviewer: dict[str, list[tuple[datetime, datetime]]] = {i: [] for i in interviewers}
    for row in rows:
        start_time = _to_time(row.get("from_time"))
        end_time = _to_time(row.get("to_time"))
        if not start_time or not end_time:
            continue
        start_dt = datetime.combine(row["scheduled_on"], start_time)
        end_dt = datetime.combine(row["scheduled_on"], end_time)
        by_interviewer.setdefault(row["interviewer"], []).append((start_dt, end_dt))
    return by_interviewer


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def get_slot_suggestions(
    interviewers: list[str],
    job_opening: str | None = None,
    days: int | None = None,
    slot_minutes: int | None = None,
    limit: int | None = None,
) -> list[SlotSuggestion]:
    interviewers = [i for i in (interviewers or []) if i]
    if not interviewers:
        return []

    days = int(days or get_conf("ai_hrms_interview_suggestion_days", 7) or 7)
    slot_minutes = int(slot_minutes or get_conf("ai_hrms_interview_slot_minutes", 60) or 60)
    limit = int(limit or get_conf("ai_hrms_interview_suggestion_limit", 10) or 10)

    work_start = get_conf("ai_hrms_interview_work_start_time")
    work_end = get_conf("ai_hrms_interview_work_end_time")

    if job_opening and frappe.db.exists("Job Opening", job_opening):
        job = frappe.get_doc("Job Opening", job_opening)
        if hasattr(job, "ai_interview_from_time") and job.get("ai_interview_from_time"):
            work_start = job.get("ai_interview_from_time")
        if hasattr(job, "ai_interview_to_time") and job.get("ai_interview_to_time"):
            work_end = job.get("ai_interview_to_time")

    start_time = _to_time(work_start)
    end_time = _to_time(work_end)
    if not start_time or not end_time:
        return []

    from_date = nowdate()
    to_date = add_days(from_date, days)

    busy = _build_ranges_by_interviewer(interviewers, from_date, to_date)

    suggestions: list[SlotSuggestion] = []
    for day_offset in range(days + 1):
        current_date = add_days(from_date, day_offset)
        cursor = datetime.combine(current_date, start_time)
        end_dt = datetime.combine(current_date, end_time)
        while cursor + frappe.utils.timedelta(minutes=slot_minutes) <= end_dt:
            slot_start = cursor
            slot_end = cursor + frappe.utils.timedelta(minutes=slot_minutes)
            available = True
            for interviewer in interviewers:
                for busy_start, busy_end in busy.get(interviewer, []):
                    if _overlaps(slot_start, slot_end, busy_start, busy_end):
                        available = False
                        break
                if not available:
                    break
            if available:
                scheduled_on = slot_start.date().isoformat()
                from_time_str = slot_start.time().strftime("%H:%M:%S")
                to_time_str = slot_end.time().strftime("%H:%M:%S")
                key = f"{scheduled_on}::{from_time_str}::{to_time_str}"
                label = f"{scheduled_on} {from_time_str} - {to_time_str}"
                suggestions.append(
                    SlotSuggestion(
                        scheduled_on=scheduled_on,
                        from_time=from_time_str,
                        to_time=to_time_str,
                        key=key,
                        label=label,
                    )
                )
                if len(suggestions) >= limit:
                    return suggestions
            cursor = slot_end

    return suggestions
