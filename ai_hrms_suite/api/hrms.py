from ai_hrms_suite.ai.pipeline import enqueue_parse_for_applicant, enqueue_rescore_for_job_opening


def on_job_applicant_created(doc, method=None):
    enqueue_parse_for_applicant(doc.name)


def on_job_applicant_updated(doc, method=None):
    enqueue_parse_for_applicant(doc.name)


def on_job_opening_updated(doc, method=None):
    enqueue_rescore_for_job_opening(doc.name)
