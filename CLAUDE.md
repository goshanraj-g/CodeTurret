# Project: CodeBouncer
AI-powered security auditor using Snowflake Cortex AI.

## Architecture
- **Engine:** Snowflake Cortex AI (llama3.1-8b / claude-3-5-sonnet) called remotely via `snowflake-connector-python`.
- **Backend:** Local Python CLI (`src/scan.py`) + logic in `src/bouncer_logic/`.
- **Dashboard:** Local Streamlit app (`src/dashboard.py`) reading from Snowflake tables.
- **Data Source:** GitHub repos cloned locally via `git clone --depth 50` (with git history for intel).
- **Smart Scanner:** Git intel + AST/regex code extraction + enriched prompts.

## Development Workflow
- **Standard:** Use `llama3.1-8b` for high-speed triage.
- **Deep Audit:** Trigger `claude-3-5-sonnet` for high-severity/low-confidence findings.
- **Verification:** Always run `pytest` after changing bouncer logic.

## Commands
- **Scan a repo:** `python src/scan.py https://github.com/user/repo`
- **Deep scan:** `python src/scan.py https://github.com/user/repo --deep`
- **Dashboard:** `streamlit run src/dashboard.py`
- **Run tests:** `pytest tests/ -v`

## Standards
- Use **parameterized queries** (`%s` placeholders) — no f-strings in SQL.
- Security results stored as JSON in Snowflake for the Streamlit heatmap.
- Credentials in `.env` file (see `.env.example`).
