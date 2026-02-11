# AI HRMS Suite (ERPNext v15 / Frappe v15)

Open-source AI-first HRMS extensions for ERPNext/Frappe HR: intelligent recruitment automation (resume parsing, JD matching, shortlisting) and an enterprise-ready HRMS chatbot with agentic actions.

## 🚀 Features

### 🤖 AI HRMS Chatbot
- **Ask Anything in HRMS**: Natural language queries about employees, leaves, payroll, attendance, recruitment, and more
- **3-Node Hybrid Architecture**: Cost-optimized pipeline using cheap models for intent analysis, zero-cost tool execution, and smart models for response generation
- **Agentic Actions**: Create and manage HR records (Leave Applications, Employees, etc.) through conversational interface with 2-step confirmation
- **Session Management**: Persistent chat sessions with history, search, rename, and delete capabilities
- **Smart Short-Circuiting**: Direct answers for simple queries (greetings, clarifications) without invoking expensive models
- **Permission-Aware**: All queries and actions respect Frappe's role-based access control
- **Floating Widget + Expandable UI**: Accessible from anywhere in the desk with expandable full-screen chat experience

### 📄 Recruitment Automation
- **Resume Parsing**: Extract structured JSON from PDF/DOCX resumes with schema validation
- **JD Matching**: Score candidates against job descriptions with match scores, strengths, gaps, and risk flags
- **Multi-LLM Provider Routing**: Support for OpenAI, Anthropic, Gemini, and OpenRouter with policy-based tier selection
- **Cost Controls**: Daily USD budget guard with tiered fallback and intelligent caching
- **Dedup Cache**: AI Cache prevents duplicate processing of identical inputs
- **Background Processing**: Async processing on RQ (`long` queue) for scalability
- **Shortlisting Automation**: Configurable thresholds per Job Opening with auto-interview creation
- **Interview Slot Suggestions**: Availability-based scheduling suggestions in Interview form
- **Audit Logging**: Complete trail of every AI run (tokens, cost, latency, provider, model)
- **Reports & Dashboards**: AI Top Candidates report, AI Skill Gap Heatmap, and dashboard charts

## 🏗️ Architecture

### Chatbot: 3-Node Hybrid Pipeline

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│ Node 1: Intent Analysis             │
│ • Query classification               │
│ • Tool suggestion                    │
│ • Confidence scoring                 │
│ • Short-answer for simple queries    │
│ Model: GPT-4o-mini (cheap)          │
└─────────────────────────────────────┘
    │
    ├─ short-circuit? ──► return short_answer (skip Node 2 + 3)
    │
    ▼
┌─────────────────────────────────────┐
│ Node 2: Tool Execution               │
│ ┌──────────┐  ┌──────────┐           │
│ │ RAG      │  │ API      │           │
│ │ Search   │  │ Calls    │           │
│ └──────────┘  └──────────┘           │
│ • Parallel execution                 │
│ • Result aggregation                 │
│ Cost: $0 (pure Frappe API)           │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Node 3: Response Generation          │
│ • Context assembly                   │
│ • Memory injection                   │
│ • Action plan generation             │
│ Model: Claude 3.5 Sonnet (smart)     │
└─────────────────────────────────────┘
    │
    ▼
Streaming Response
```

**Cost Optimization:**
- Node 1 uses cheap models (GPT-4o-mini) for classification
- Node 2 has zero LLM cost (pure API calls)
- Node 3 only invoked when needed (complex queries, agentic actions)
- Short-circuiting for greetings/clarifications saves ~70% of costs
- Intelligent caching prevents duplicate processing

## 📦 Installation

```bash
# Install the app
bench --site <site> install-app ai_hrms_suite
bench --site <site> migrate
bench restart

# Install Python dependencies
pip install pdfplumber python-docx jinja2 requests jsonschema redis

# Start background worker (for recruitment automation)
bench worker --queue long
```

## ⚙️ Configuration

All AI HRMS settings are managed via the **AI HRMS Settings** DocType (no need to edit `site_config.json`).

1. Navigate to **AI HRMS Settings** in the desk
2. Configure the following sections:

### Provider API Keys
- OpenAI API Key
- Anthropic API Key
- Gemini API Key
- OpenRouter API Key

### General Settings
- **Enable Cache**: Toggle AI Cache for deduplication
- **Daily Budget (USD)**: Daily cap for AI spend
- **Max Resume Chars**: Maximum characters sent to models (default: 20000)
- **Max Prompt Tokens**: Router guard for prompt size (default: 6000)
- **Store Raw Text**: Whether to store extracted resume text in DB

### Model Policies (Child Table)
Define LLM provider and model for each task:
- **Task Name**: `resume_parse`, `jd_match`, `intent_analysis`, `response_gen`
- **Provider**: `openai`, `anthropic`, `gemini`, `openrouter`
- **Model**: Provider-specific model identifier (e.g., `gpt-4o-mini`, `claude-3-5-sonnet-20241022`)
- **Priority**: Lower number = tried first (fallback chain)

**Example Policy Configuration:**
```
Task: intent_analysis
  → Priority 1: openai/gpt-4o-mini
  → Priority 2: openrouter/openai/gpt-4o-mini

Task: response_gen
  → Priority 1: anthropic/claude-3-5-sonnet-20241022
  → Priority 2: openai/gpt-4o
```

### Shortlisting Settings
- **Default Threshold**: Match score threshold for auto-shortlisting (0-100)
- **Send Email on Shortlist**: Enable email notifications
- **Email Subject**: Custom subject line
- **Email Recipients**: Comma-separated list or array

### Interview Automation
- **Auto Create Interview**: Enable automatic interview creation on shortlist
- **Default Interview Round**: Default round name
- **Offset Days**: Days after today to schedule (default: 3)
- **From Time / To Time**: Default interview time window

### Interview Slot Suggestions
- **Suggestion Days**: Search window in days (default: 14)
- **Slot Minutes**: Length of each slot (default: 60)
- **Suggestion Limit**: Maximum suggestions (default: 5)
- **Work Start/End Time**: Workday boundaries

## 📖 Usage

### Chatbot

1. **Access the Chatbot**:
   - Look for the floating **AI HRMS Assistant** widget in the bottom-right corner
   - Click to open the chat interface
   - Click the expand icon (four corners) to open full-screen chat with session management

2. **Ask Questions**:
   - Type natural language questions: "How do I apply for leave?", "Show me pending leave applications", "What is payroll processing?"
   - The chatbot understands HRMS context and provides accurate answers

3. **Agentic Actions**:
   - Request actions: "Create a leave application", "Add a new employee"
   - Review the action preview card
   - Click **Confirm** to execute (requires appropriate permissions)

4. **Session Management**:
   - Click **+ New chat** to start a fresh conversation
   - Use the sidebar to switch between sessions
   - Search, rename, or delete sessions as needed

### Recruitment Automation

1. **Ensure Background Worker is Running**:
   ```bash
   bench worker --queue long
   ```

2. **Create a Job Opening**:
   - Add a detailed job description
   - The system will use this for JD matching

3. **Process Job Applicants**:
   - Create a Job Applicant and attach a PDF/DOCX resume
   - The system automatically:
     - Parses the resume into structured JSON (`AI Resume Parse Result`)
     - Scores the candidate against the Job Opening (`AI Screening Scorecard`)
     - Auto-shortlists if score exceeds threshold
     - Creates interview (if enabled) and sends notifications

4. **Review Results**:
   - Check `AI Resume` and `AI Resume Parse Result` for structured data
   - Review `AI Screening Scorecard` for match scores, strengths, gaps
   - Use reports and dashboards for pipeline analysis

5. **Interview Scheduling**:
   - Open an Interview form
   - Click **Suggest Slots** for availability-based suggestions

## 🔌 API Endpoints

All endpoints require authentication (Frappe session).

### Chatbot APIs

- `ai_hrms_suite.api.chatbot.ask(question, session_id=None)`: Ask an HRMS question
- `ai_hrms_suite.api.chatbot.list_sessions(limit=50)`: List user's chat sessions
- `ai_hrms_suite.api.chatbot.create_session(title=None)`: Create a new session
- `ai_hrms_suite.api.chatbot.rename_session(session_id, title)`: Rename a session
- `ai_hrms_suite.api.chatbot.delete_session(session_id)`: Delete a session
- `ai_hrms_suite.api.chatbot.get_messages(session_id, limit=50)`: Get session messages
- `ai_hrms_suite.api.chatbot.confirm_action(session_id, message_id)`: Execute a pending action

### Recruitment APIs

- `ai_hrms_suite.api.hrms.on_job_applicant_updated`: Triggered on Job Applicant update (resume parsing)
- `ai_hrms_suite.api.hrms.on_job_opening_updated`: Triggered on Job Opening update (rescoring)

## 📋 DocTypes

### Chatbot
- **AI Chat Session**: Stores chat sessions with user, title, status, timestamps
- **AI Chat Message**: Individual messages with role, content, sources, action plans, LLM metadata
- **AI HRMS Settings**: Single DocType for all AI configurations (replaces `site_config.json`)
- **AI Model Policy**: Child table for defining LLM policies per task

### Recruitment
- **AI Resume**: Links to Job Applicant resume files
- **AI Resume Parse Result**: Structured JSON output from resume parsing
- **AI Screening Scorecard**: JD match scores, strengths, gaps, risk flags
- **AI Run Log**: Audit trail of every AI operation (tokens, cost, latency, provider, model)
- **AI Cache**: Deduplication cache for identical inputs

## 🎯 Benefits

### Cost Efficiency
- **70% cost reduction** via short-circuiting and intelligent routing
- Daily budget caps prevent overspending
- Caching eliminates duplicate processing
- Hybrid architecture uses cheap models where possible

### Accuracy & Reliability
- Schema-validated outputs ensure data consistency
- Permission-aware queries respect access control
- Multi-tier fallback ensures high availability
- Complete audit trail for debugging and compliance

### User Experience
- Natural language interface for HRMS operations
- Persistent sessions with full history
- Agentic actions reduce manual data entry
- Expandable UI accessible from anywhere

### Operational Speed
- Automated shortlisting reduces manual screening time
- Interview slot suggestions optimize scheduling
- Background processing doesn't block user workflows
- Real-time chatbot responses for instant answers

## 🔮 Future Enhancements

- [ ] OCR support for scanned PDF resumes
- [ ] Multi-language support for chatbot
- [ ] Voice input/output for chatbot
- [ ] Advanced analytics and insights dashboard
- [ ] Integration with external HR tools
- [ ] Custom workflow automation via chatbot
- [ ] Batch processing for bulk resume parsing
- [ ] Enhanced action preview with field-level validation

## 📝 Notes

- **Raw Text Storage**: Disabled by default (`store_raw_text=false`) for privacy
- **Resume Size Limits**: Keep max chars low (e.g., 20k) for stability and cost control
- **Queue Worker**: Must run `bench worker --queue long` for recruitment automation
- **Redis Cache**: Recommended for optimal performance (settings cache, HRMS module lists)
- **Permissions**: All chatbot queries and actions respect Frappe role-based permissions
- **Session Ownership**: Users can only access their own chat sessions

## 🤝 Contributing

This is an open-source project. Contributions are welcome!

## 📄 License

MIT License - see `license.txt` for details.
