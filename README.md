# AI HRMS Suite (ERPNext v15 / Frappe v15)

AI-first HRMS extensions for ERPNext hiring workflows: parse resumes into strict JSON, score candidates against JDs, and automate shortlisting/interviews with full audit trails.

## Features
- Resume parsing for PDF/DOCX into strict JSON with schema validation
- JD ↔ resume screening scorecards: match score, strengths, gaps, risk flags, explanation
- Multi-LLM provider routing with policy tiers (OpenAI, Anthropic, Gemini, OpenRouter)
- Cost controls: daily USD budget guard + tiered fallback
- Dedup cache for identical inputs (AI Cache)
- Background processing on RQ (`long` queue)
- Shortlisting automation with configurable thresholds per Job Opening
- Optional auto interview creation and email notification on shortlist
- Interview slot suggestions in Interview form (button + API)
- Audit logging for every AI run (tokens, cost, latency)
- Reports: AI Top Candidates, AI Skill Gap Heatmap
- Dashboard charts: AI Shortlisted by Job, AI Skill Gap Heatmap

## Install
```bash
bench --site <site> install-app ai_hrms_suite
bench --site <site> migrate
bench restart
pip install pdfplumber python-docx jinja2 requests jsonschema
```

## Configuration
Edit `sites/<site>/site_config.json` and add your keys + policies.

Provider API keys (as required by your provider library):
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`

Core routing + limits:
- `ai_hrms_policies`: policy tiers per task (`resume_parse`, `jd_match`)
- `ai_hrms_enable_cache`: enable/disable AI Cache
- `ai_hrms_budget_usd_per_day`: daily cap for AI spend
- `ai_hrms_max_resume_chars`: max chars sent to the model
- `ai_hrms_max_prompt_tokens`: max prompt tokens (router guard)
- `ai_hrms_store_raw_text`: store extracted resume text in DB

Shortlisting + notifications:
- `ai_hrms_shortlist_threshold`: default match score threshold
- `ai_hrms_shortlist_send_email`: enable email notification on shortlist
- `ai_hrms_shortlist_email_subject`: email subject
- `ai_hrms_shortlist_email_recipients`: comma list or array

Interview automation:
- `ai_hrms_auto_create_interview`: enable auto interview creation
- `ai_hrms_default_interview_round`: default Interview Round
- `ai_hrms_interview_offset_days`: days after today to schedule
- `ai_hrms_interview_from_time`: default from time
- `ai_hrms_interview_to_time`: default to time

Interview slot suggestions:
- `ai_hrms_interview_suggestion_days`: search window (days)
- `ai_hrms_interview_slot_minutes`: slot length (minutes)
- `ai_hrms_interview_suggestion_limit`: max suggestions
- `ai_hrms_interview_work_start_time`: workday start
- `ai_hrms_interview_work_end_time`: workday end

## How It Works
1. When a Job Applicant is created/updated with a resume, a parse job is enqueued.
2. Parsed JSON is saved in `AI Resume Parse Result`.
3. If the applicant is linked to a Job Opening, a scoring job is enqueued.
4. Screening results are saved in `AI Screening Scorecard`, and shortlist logic runs.

## Usage
1. Ensure the `long` queue worker is running:
   `bench worker --queue long`
2. Create a Job Opening with a description.
3. Create a Job Applicant and attach a PDF/DOCX resume.
4. Review:
   - `AI Resume` and `AI Resume Parse Result` for structured data
   - `AI Screening Scorecard` for match score + gaps/strengths
5. Use reports and dashboards to analyze hiring pipelines.
6. Open an Interview and use **Suggest Slots** for availability-based suggestions.

## DocTypes Added
- AI Resume
- AI Resume Parse Result
- AI Screening Scorecard
- AI Run Log
- AI Cache

## Benefits
- Faster screening with consistent, structured resume data
- Higher hiring quality via explainable JD match scoring
- Lower AI costs using cache + policy-based routing + budget caps
- Operational speedups with auto shortlisting and interview scheduling
- Better visibility with reports, charts, and audit logs

## Future Enhancements
- OCR for scanned PDFs

## Notes
- Raw text is not stored by default (`ai_hrms_store_raw_text=false`).
- Keep resume max chars low (e.g., 20k) for stability.
- OCR for scanned PDFs is not included yet.
- Your resume field may be named differently; update the field lookup if needed:
  `resume` or `resume_attachment`.
