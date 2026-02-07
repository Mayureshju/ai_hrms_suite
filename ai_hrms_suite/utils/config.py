import frappe


def get_conf(key: str, default=None):
    # frappe.conf already merges site_config
    return frappe.conf.get(key, default)


def get_policies():
    return get_conf("ai_hrms_policies", {}) or {}
