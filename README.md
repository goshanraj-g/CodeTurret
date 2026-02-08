# CodeBouncer

**AI-Powered Security Auditor** — Autonomous vulnerability detection and remediation for your codebase.

![Made with Gemini](https://img.shields.io/badge/AI-Gemini%202.0-blue)
![Snowflake](https://img.shields.io/badge/Data-Snowflake-29B5E8)
![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-black)

## Features

- 🔍 **Dual-Pass AI Scanning** — Gemini Flash for fast triage, Gemini Pro for deep analysis
- 🧠 **Git Intelligence** — Prioritizes files based on commit history and security-related changes
- 💬 **Ask Cortex** — Natural language Q&A about your scan results using Snowflake Cortex
- 🎯 **Severity Ranking** — Findings sorted by CRITICAL → HIGH → MEDIUM → LOW
- 🖥️ **Modern Dashboard** — Dark-mode UI with real-time scan logs

---

## How Gemini AI Powers the Scanner

CodeBouncer uses a **two-pass scanning architecture** with Google's Gemini models:

### Pass 1: Rapid Triage (Gemini 2.0 Flash)
- Scans all prioritized files in parallel
- Uses structured JSON output schema for consistent findings
- Identifies potential vulnerabilities with severity + confidence scores
- Ultra-fast (~1-2s per file) for quick initial assessment

### Pass 2: Deep Analysis (Gemini 2.5 Pro)
- Only runs on files flagged as HIGH/CRITICAL risk
- Performs semantic analysis of code patterns
- Generates detailed fix suggestions with corrected code snippets
- Validates triage findings and reduces false positives

**Prompt Engineering**: Each prompt includes:
- File role context (e.g., "authentication handler", "API endpoint")
- Git history signals (recent security commits, high-churn files)
- Repository context from README/docs

---

## How Snowflake Stores & Analyzes Results

Snowflake serves as the **data backbone** for CodeBouncer:

### 1. Persistent Storage
| Table | Purpose |
|-------|---------|
| `REPOSITORY_CONFIG` | Registered repos and their metadata |
| `SCAN_HISTORY` | Audit log of all scans with status/timestamps |
| `SCAN_RESULTS` | Individual vulnerability findings per scan |

### 2. Cortex LLM Integration
The `/ask` endpoint uses **Snowflake Cortex** (`llama3.1-8b`) to answer natural language questions:

```
User: "What are the most common vulnerability types in my-app?"
Cortex: "Based on 47 findings across 8 scans, SQL Injection (34%) and 
        XSS (28%) are the most frequent. The auth/ directory has the 
        highest concentration of critical issues."
```

### 3. Analytics Views
- `SCAN_HEATMAP` — Aggregated severity counts by file path
- Enables trend analysis and hotspot identification over time


## Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| **AI**      | Gemini 2.0 Flash + Gemini 2.5 Pro   |
| **Backend** | Python, FastAPI                     |
| **Frontend**| Next.js 16, Tailwind CSS, Framer Motion |
| **Database**| Snowflake + Cortex LLM              |

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/goshanraj-g/CodeBouncer.git
cd CodeBouncer
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
```

### 3. Run Backend

```bash
python -m uvicorn src.api:app --reload
```

API available at `http://localhost:8000` (Swagger docs at `/docs`).

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## API Endpoints

| Method | Endpoint             | Description                      |
|--------|----------------------|----------------------------------|
| POST   | `/scan`              | Trigger a security scan          |
| GET    | `/scans`             | List recent scan history         |
| GET    | `/findings/{scan_id}`| Get findings for a scan          |
| POST   | `/ask`               | Ask Cortex about scan results    |
| GET    | `/repos`             | List configured repositories     |

## Project Structure

```
CodeBouncer/
├── frontend/           # Next.js web UI
│   ├── app/            # Pages (Dashboard, Scanner, Findings, Ask)
│   └── components/     # CircularNav, TerminalOutput
├── src/
│   ├── api.py          # FastAPI backend
│   └── bouncer_logic/  # Core scanning engine
│       ├── scanner.py      # Orchestrator
│       ├── gemini_client.py# AI client (google-genai)
│       ├── prompts.py      # Prompt engineering
│       └── repo_chat.py    # Cortex Q&A
├── sql/                # Snowflake schema setup
└── tests/              # Unit tests
```

## License

MIT