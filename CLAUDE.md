# 🛡️ Project: CodeBouncer
AI-powered security auditor running natively in Snowflake.

## 🏗️ Architecture
- **Engine:** Snowflake Cortex AI (Gemini 3.0 Flash/Pro).
- **Backend:** Snowpark Python (Logic in `src/bouncer_logic/`).
- **Dashboard:** Streamlit in Snowflake (`src/dashboard.py`).
- **Data Source:** GitHub via Snowflake Native Git Integration.

## 🛠️ Development Workflow
- **Standard:** Use `gemini-3.0-flash` for high-speed metadata and summaries.
- **Deep Audit:** Trigger `gemini-3.0-pro` for vulnerability logic reasoning.
- **Verification:** Always run `pytest` after changing bouncer logic.

## 📋 Commands
- **Sync GitHub:** `ALTER GIT REPOSITORY GITHUB_REPO FETCH;`
- **Deploy App:** `snow streamlit deploy`
- **Manual Scan:** `CALL RUN_SECURITY_SCAN();`

## ⚠️ Standards
- Use **parameterized queries** in Snowpark (No f-strings in SQL!).
- Security results MUST be JSON-formatted for the Streamlit heatmap.