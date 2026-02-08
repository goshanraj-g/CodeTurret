"""Repo Q&A — ask natural language questions about scan results.

Uses Snowflake Cortex COMPLETE to answer questions based on
findings stored in SCAN_RESULTS and SCAN_HISTORY tables.
"""

import json
import logging
from typing import Optional

from bouncer_logic import config

logger = logging.getLogger(__name__)


class RepoChatError(Exception):
    """Raised when a repo chat query fails."""


def ask_about_repo(conn, repo_name: str, question: str) -> str:
    """Answer a natural language question about a repo's scan results.

    Fetches the latest scan context from Snowflake, builds a prompt
    with all findings, and calls Cortex COMPLETE for an answer.

    Returns the answer string, or an error message if no data exists.
    """
    context = _get_repo_context(conn, repo_name)
    if context is None:
        return f"No scan data found for repository '{repo_name}'. Run a scan first."

    prompt = _build_chat_prompt(context, repo_name, question)
    return _call_cortex(conn, prompt)


def _get_repo_context(conn, repo_name: str) -> Optional[dict]:
    """Query Snowflake for the latest scan data for a repo.

    Returns a dict with scan metadata, severity counts, and findings,
    or None if no scans exist for this repo.
    """
    cur = conn.cursor()
    try:
        # Get latest completed scan for this repo
        cur.execute(
            """SELECT sh.SCAN_ID, sh.FILES_SCANNED, sh.FINDINGS_COUNT,
                      sh.STARTED_AT, sh.STATUS
               FROM CODEBOUNCER.CORE.SCAN_HISTORY sh
               JOIN CODEBOUNCER.CORE.REPOSITORY_CONFIG rc
                 ON sh.REPO_ID = rc.REPO_ID
               WHERE rc.REPO_NAME = %s
                 AND sh.STATUS = 'COMPLETED'
               ORDER BY sh.STARTED_AT DESC
               LIMIT 1""",
            (repo_name,),
        )
        scan_row = cur.fetchone()
        if not scan_row:
            return None

        scan_id, files_scanned, findings_count, started_at, status = scan_row

        # Get severity distribution
        cur.execute(
            """SELECT SEVERITY, COUNT(*) AS CNT
               FROM CODEBOUNCER.CORE.SCAN_RESULTS
               WHERE SCAN_ID = %s
               GROUP BY SEVERITY
               ORDER BY
                 CASE SEVERITY
                   WHEN 'CRITICAL' THEN 1
                   WHEN 'HIGH' THEN 2
                   WHEN 'MEDIUM' THEN 3
                   ELSE 4
                 END""",
            (scan_id,),
        )
        severity_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Get all findings for this scan
        cur.execute(
            """SELECT SEVERITY, VULN_TYPE, DESCRIPTION, FILE_PATH,
                      FIX_SUGGESTION, CONFIDENCE, LINE_NUMBER
               FROM CODEBOUNCER.CORE.SCAN_RESULTS
               WHERE SCAN_ID = %s
               ORDER BY
                 CASE SEVERITY
                   WHEN 'CRITICAL' THEN 1
                   WHEN 'HIGH' THEN 2
                   WHEN 'MEDIUM' THEN 3
                   ELSE 4
                 END,
                 CONFIDENCE DESC""",
            (scan_id,),
        )
        columns = [desc[0] for desc in cur.description]
        findings = [dict(zip(columns, row)) for row in cur.fetchall()]

        return {
            "scan": {
                "scan_id": scan_id,
                "files_scanned": files_scanned,
                "findings_count": findings_count,
                "started_at": str(started_at),
                "status": status,
            },
            "severity_counts": severity_counts,
            "findings": findings,
        }

    finally:
        cur.close()


def _build_chat_prompt(context: dict, repo_name: str, question: str) -> str:
    """Build a prompt with full scan context and the user's question."""
    scan = context["scan"]
    severity_counts = context["severity_counts"]
    findings = context["findings"]

    # Format severity distribution
    severity_str = ", ".join(
        f"{sev}: {cnt}" for sev, cnt in severity_counts.items()
    )

    # Format findings list
    findings_lines = []
    for i, f in enumerate(findings, 1):
        line_info = f":{f['LINE_NUMBER']}" if f.get("LINE_NUMBER") else ""
        entry = (
            f"{i}. [{f['SEVERITY']}] {f['VULN_TYPE']} in "
            f"{f['FILE_PATH']}{line_info} — {f['DESCRIPTION']} "
            f"(confidence: {f['CONFIDENCE']})"
        )
        if f.get("FIX_SUGGESTION"):
            entry += f"\n   Fix: {f['FIX_SUGGESTION']}"
        findings_lines.append(entry)

    findings_text = "\n".join(findings_lines) if findings_lines else "No findings."

    return (
        "You are a security analyst assistant. Answer questions about "
        "this repository's security scan results. Be specific and reference "
        "actual findings when relevant.\n\n"
        f"REPOSITORY: {repo_name}\n"
        f"LAST SCAN: {scan['started_at']} — {scan['files_scanned']} files "
        f"scanned, {scan['findings_count']} findings\n"
        f"SEVERITY DISTRIBUTION: {severity_str}\n\n"
        f"FINDINGS:\n{findings_text}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer concisely based on the scan data above. If the data doesn't "
        "contain enough information to answer, say so."
    )


def _call_cortex(conn, prompt: str) -> str:
    """Call Snowflake Cortex COMPLETE and return the response text."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
            (config.CORTEX_CHAT_MODEL, prompt),
        )
        result = cur.fetchone()
        if not result:
            raise RepoChatError("Empty response from Cortex")

        raw = result[0]
        parsed = json.loads(raw) if isinstance(raw, str) else raw

        if isinstance(parsed, dict) and "choices" in parsed:
            msg = parsed["choices"][0]["messages"]
            return msg if isinstance(msg, str) else json.dumps(msg)
        return str(parsed)

    except RepoChatError:
        raise
    except Exception as exc:
        logger.warning("Cortex chat call failed: %s", exc)
        raise RepoChatError(f"Failed to get answer from Cortex: {exc}") from exc
    finally:
        cur.close()
