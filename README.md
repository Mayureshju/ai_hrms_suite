# AI HRMS Suite (ERPNext v15 / Frappe v15)

Open-source AI extensions for ERPNext HRMS:
- Resume parsing (PDF/DOCX) → strict JSON
- JD ↔ Resume screening scorecard (strict JSON)
- Multi-LLM providers: OpenAI, Anthropic, Gemini, OpenRouter
- Cost-optimized routing: tier ladder + schema validation + fallback
- Dedup cache via DocType (AI Cache)
- Background processing via RQ workers
- Audit logging via AI Run Log

## Install
```bash
bench --site <site> install-app ai_hrms_suite
bench --site <site> migrate
bench restart
pip install pdfplumber python-docx jinja2 requests jsonschema

Configure

Edit sites/<site>/site_config.json:

API keys for providers

ai_hrms_policies for task tier routing

ai_hrms_budget_usd_per_day, ai_hrms_enable_cache, max chars

How it works

Job Applicant create/update (with resume field) triggers parse job

Parse result stored in AI Resume Parse Result

If applicant has job_opening link, scoring job runs and stores AI Screening Scorecard

Worker
bench worker --queue long

Notes

Raw text is not stored by default (ai_hrms_store_raw_text=false)

For best stability, keep resume max chars low (20k)

Add OCR later for scanned PDFs


---

# 17) Final migrate + restart

```bash
bench --site <site> migrate
bench restart


Test:

Create Job Opening with description

Create Job Applicant and attach resume (PDF/DOCX) in your resume field

Ensure worker running: bench worker --queue long

Check DocTypes: AI Resume, AI Resume Parse Result, AI Screening Scorecard, AI Run Log, AI Cache

Important note (so it works in YOUR ERPNext)

Your Job Applicant resume field might not be resume or resume_attachment.

In pipeline.py these lines decide it:

file_url = getattr(applicant, "resume", None) or getattr(applicant, "resume_attachment", None) make sure you follow industry level standard and well optimized 
