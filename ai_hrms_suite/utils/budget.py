import frappe
from datetime import date

from ai_hrms_suite.utils.config import get_conf


def _today_key() -> str:
    return date.today().isoformat()


def get_daily_budget_usd() -> float:
    return float(get_conf("budget_usd_per_day", 0) or 0.0)


def get_spent_today_usd() -> float:
    # Sum cost from AI Run Log for today
    d = _today_key()
    row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(cost_usd),0)
        FROM `tabAI Run Log`
        WHERE DATE(creation) = %s
          AND status = 'Success'
        """,
        (d,),
        as_list=True
    )
    return float(row[0][0] or 0.0)


def assert_within_budget(extra_cost_usd: float = 0.0):
    budget = get_daily_budget_usd()
    if budget <= 0:
        return  # budget disabled
    spent = get_spent_today_usd()
    if spent + float(extra_cost_usd or 0.0) > budget:
        raise RuntimeError(f"AI budget exceeded for today. Spent={spent:.2f}, Budget={budget:.2f}")
