"""Snowflake Cortex analytics — post-scan insights on stored findings.

Scanning is handled by gemini_client.py.  This module uses Snowflake Cortex
built-in functions (SUMMARIZE, COMPLETE) to generate analytics on findings
already persisted in Snowflake tables.
"""

import json
import logging

from bouncer_logic import config

logger = logging.getLogger(__name__)


class CortexCallError(Exception):
    """Raised when a Cortex analytics call fails."""


def summarize_findings(conn, scan_id: str) -> str:
    """Use Cortex COMPLETE to produce a human-readable scan summary.

    Reads findings from SCAN_RESULTS for the given scan_id, sends them
    to the analytics LLM, and returns a markdown summary string.
    """
    cur = conn.cursor()
    try:
        # Pull findings for this scan
        cur.execute(
            """SELECT FILE_PATH, SEVERITY, VULN_TYPE, DESCRIPTION, CONFIDENCE
               FROM CODEBOUNCER.CORE.SCAN_RESULTS
               WHERE SCAN_ID = %s
               ORDER BY SEVERITY, CONFIDENCE DESC""",
            (scan_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return "No findings to summarize."

        columns = [desc[0] for desc in cur.description]
        findings = [dict(zip(columns, row)) for row in rows]
        findings_text = json.dumps(findings, indent=2)

        prompt = (
            "Summarize the following security scan findings into a concise "
            "executive report (3-5 bullet points). Group by severity, "
            "highlight the most critical issues, and suggest priority order "
            "for remediation.\n\n"
            f"FINDINGS:\n{findings_text}"
        )

        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
            (config.CORTEX_ANALYTICS_MODEL, prompt),
        )
        result = cur.fetchone()
        raw = result[0]
        parsed = json.loads(raw) if isinstance(raw, str) else raw

        if isinstance(parsed, dict) and "choices" in parsed:
            msg = parsed["choices"][0]["messages"]
            return msg if isinstance(msg, str) else json.dumps(msg)
        return str(parsed)

    except Exception as exc:
        logger.warning("Cortex summarize_findings failed: %s", exc)
        raise CortexCallError(f"Failed to summarize findings: {exc}") from exc
    finally:
        cur.close()


def classify_severity_trend(conn, repo_name: str) -> dict:
    """Analyze severity trends across recent scans for a repo.

    Returns a dict with trend direction and breakdown.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT sh.SCAN_ID, sh.STARTED_AT,
                      sr.SEVERITY, COUNT(*) AS CNT
               FROM CODEBOUNCER.CORE.SCAN_HISTORY sh
               JOIN CODEBOUNCER.CORE.REPOSITORY_CONFIG rc
                 ON sh.REPO_ID = rc.REPO_ID
               JOIN CODEBOUNCER.CORE.SCAN_RESULTS sr
                 ON sh.SCAN_ID = sr.SCAN_ID
               WHERE rc.REPO_NAME = %s
                 AND sh.STATUS = 'COMPLETED'
               GROUP BY sh.SCAN_ID, sh.STARTED_AT, sr.SEVERITY
               ORDER BY sh.STARTED_AT DESC
               LIMIT 50""",
            (repo_name,),
        )
        rows = cur.fetchall()
        if not rows:
            return {"trend": "no_data", "scans": []}

        columns = [desc[0] for desc in cur.description]
        data = [dict(zip(columns, row)) for row in rows]

        prompt = (
            "Analyze the following severity counts across scans and determine "
            "the trend (improving, worsening, stable). Return JSON with keys: "
            "trend (string), summary (string), severity_breakdown (object).\n\n"
            f"DATA:\n{json.dumps(data, indent=2, default=str)}"
        )

        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
            (config.CORTEX_ANALYTICS_MODEL, prompt),
        )
        result = cur.fetchone()
        raw = result[0]
        parsed = json.loads(raw) if isinstance(raw, str) else raw

        if isinstance(parsed, dict) and "choices" in parsed:
            msg = parsed["choices"][0]["messages"]
            return json.loads(msg) if isinstance(msg, str) else msg
        return parsed if isinstance(parsed, dict) else {"trend": "unknown", "raw": str(parsed)}

    except Exception as exc:
        logger.warning("Cortex classify_severity_trend failed: %s", exc)
        return {"trend": "error", "error": str(exc)}
    finally:
        cur.close()


def get_scan_insights(conn, scan_id: str) -> dict:
    """Generate AI-powered insights for a completed scan.

    Combines finding data with Cortex COMPLETE to produce actionable insights.
    Returns a dict with keys: summary, risk_level, top_recommendations.
    """
    cur = conn.cursor()
    try:
        # Get scan metadata
        cur.execute(
            """SELECT sh.FILES_SCANNED, sh.FINDINGS_COUNT,
                      rc.REPO_NAME
               FROM CODEBOUNCER.CORE.SCAN_HISTORY sh
               JOIN CODEBOUNCER.CORE.REPOSITORY_CONFIG rc
                 ON sh.REPO_ID = rc.REPO_ID
               WHERE sh.SCAN_ID = %s""",
            (scan_id,),
        )
        meta = cur.fetchone()
        if not meta:
            return {"error": "Scan not found"}

        files_scanned, findings_count, repo_name = meta

        # Get severity distribution
        cur.execute(
            """SELECT SEVERITY, COUNT(*) AS CNT
               FROM CODEBOUNCER.CORE.SCAN_RESULTS
               WHERE SCAN_ID = %s
               GROUP BY SEVERITY""",
            (scan_id,),
        )
        severity_rows = cur.fetchall()
        severity_dist = {row[0]: row[1] for row in severity_rows}

        # Get top findings for context
        cur.execute(
            """SELECT SEVERITY, VULN_TYPE, DESCRIPTION, FILE_PATH
               FROM CODEBOUNCER.CORE.SCAN_RESULTS
               WHERE SCAN_ID = %s
               ORDER BY
                 CASE SEVERITY
                   WHEN 'CRITICAL' THEN 1
                   WHEN 'HIGH' THEN 2
                   WHEN 'MEDIUM' THEN 3
                   ELSE 4
                 END,
                 CONFIDENCE DESC
               LIMIT 10""",
            (scan_id,),
        )
        top_rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        top_findings = [dict(zip(columns, row)) for row in top_rows]

        prompt = (
            f"Analyze this security scan of '{repo_name}':\n"
            f"- Files scanned: {files_scanned}\n"
            f"- Total findings: {findings_count}\n"
            f"- Severity distribution: {json.dumps(severity_dist)}\n"
            f"- Top findings: {json.dumps(top_findings, indent=2)}\n\n"
            "Return JSON with keys:\n"
            "- risk_level: CRITICAL/HIGH/MEDIUM/LOW\n"
            "- summary: 2-3 sentence overview\n"
            "- top_recommendations: array of 3-5 prioritized action items\n"
            "- patterns: array of recurring vulnerability patterns found"
        )

        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
            (config.CORTEX_ANALYTICS_MODEL, prompt),
        )
        result = cur.fetchone()
        raw = result[0]
        parsed = json.loads(raw) if isinstance(raw, str) else raw

        if isinstance(parsed, dict) and "choices" in parsed:
            msg = parsed["choices"][0]["messages"]
            return json.loads(msg) if isinstance(msg, str) else msg
        return parsed if isinstance(parsed, dict) else {"summary": str(parsed)}

    except Exception as exc:
        logger.warning("Cortex get_scan_insights failed: %s", exc)
        return {"error": str(exc)}
    finally:
        cur.close()
