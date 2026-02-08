frappe.query_reports["AI Skill Gap Heatmap"] = {
  "filters": [
    {
      "fieldname": "job_opening",
      "label": "Job Opening",
      "fieldtype": "Link",
      "options": "Job Opening"
    },
    {
      "fieldname": "min_score",
      "label": "Min Score",
      "fieldtype": "Float",
      "default": 0
    },
    {
      "fieldname": "days",
      "label": "Lookback Days",
      "fieldtype": "Int",
      "default": 90
    }
  ]
};
