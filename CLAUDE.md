# Project: CodeBouncer
AI-powered security auditor using Gemini AI for scanning + Snowflake for storage & analytics.

## Architecture
- **Scanning Engine:** Google Gemini API (`gemini-2.0-flash` triage, `gemini-2.5-pro` deep analysis) via `google-generativeai` SDK.
- **Storage & Analytics:** Snowflake tables + Cortex AI (`llama3.1-8b`) for post-scan insights + repo Q&A.
- **Backend:** Local Python CLI (`src/scan.py`) + logic in `src/bouncer_logic/`.
- **Dashboard:** Local Streamlit app (`src/dashboard.py`) reading from Snowflake tables.
- **Data Source:** GitHub repos cloned locally via `git clone --depth 50` (with git history for intel).
- **Smart Scanner:** Git intel + AST/regex code extraction + enriched prompts.

## Development Workflow
- **Standard:** Use `gemini-2.0-flash` for high-speed triage.
- **Deep Audit:** Trigger `gemini-2.5-pro-preview-05-06` for high-severity/low-confidence findings.
- **Post-Scan:** Snowflake Cortex generates analytics insights on persisted findings.
- **Verification:** Always run `pytest` after changing bouncer logic.

## Commands
- **Scan a repo:** `python src/scan.py https://github.com/user/repo`
- **Deep scan:** `python src/scan.py https://github.com/user/repo --deep`
- **Ask about a repo:** `python src/ask.py <repo_name> "your question"`
- **Dashboard:** `streamlit run src/dashboard.py`
- **Run tests:** `pytest tests/ -v`

## Standards
- Use **parameterized queries** (`%s` placeholders) — no f-strings in SQL.
- Security results stored as JSON in Snowflake for the Streamlit heatmap.
- Credentials in `.env` file (see `.env.example`).
