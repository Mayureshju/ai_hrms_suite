frappe.query_reports["AI Top Candidates"] = {
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
      "default": 70
    },
    {
      "fieldname": "limit",
      "label": "Limit",
      "fieldtype": "Int",
      "default": 25
    }
  ]
};
