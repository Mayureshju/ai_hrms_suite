RESUME_PARSE_SCHEMA = {
  "type": "object",
  "required": ["name", "email", "phone", "skills", "experience_years", "education"],
  "properties": {
    "name": {"type": "string"},
    "email": {"type": "string"},
    "phone": {"type": "string"},
    "skills": {"type": "array", "items": {"type": "string"}},
    "experience_years": {"type": "number"},
    "education": {"type": "array", "items": {
      "type": "object",
      "required": ["degree", "institution"],
      "properties": {
        "degree": {"type": "string"},
        "institution": {"type": "string"},
        "year": {"type": "string"}
      }
    }},
    "work_history": {"type": "array", "items": {
      "type": "object",
      "properties": {
        "company": {"type": "string"},
        "title": {"type": "string"},
        "start": {"type": "string"},
        "end": {"type": "string"},
        "summary": {"type": "string"}
      }
    }}
  }
}

JD_MATCH_SCHEMA = {
  "type": "object",
  "required": ["match_score", "strengths", "gaps", "risk_flags", "explanation"],
  "properties": {
    "match_score": {"type": "number", "minimum": 0, "maximum": 100},
    "strengths": {"type": "array", "items": {"type": "string"}},
    "gaps": {"type": "array", "items": {"type": "string"}},
    "risk_flags": {"type": "array", "items": {"type": "string"}},
    "explanation": {"type": "string"}
  }
}
