import frappe
from frappe.model.document import Document

from ai_hrms_suite.utils.config import clear_settings_cache


class AIHRMSSettings(Document):
    def on_update(self):
        clear_settings_cache()
