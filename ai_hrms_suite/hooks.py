app_name = "ai_hrms_suite"
app_title = "AI HRMS Suite"
app_publisher = "Open Source"
app_description = "Open-source AI extensions for ERPNext HRMS (Resume parsing + Screening) with multi-LLM routing."
app_email = "dev@example.com"
app_license = "MIT"

doc_events = {
    "Job Applicant": {
        "on_update": "ai_hrms_suite.api.hrms.on_job_applicant_updated",
    },
    "Job Opening": {
        "on_update": "ai_hrms_suite.api.hrms.on_job_opening_updated",
    }
}

doctype_js = {
    "Interview": "public/js/interview.js",
}
