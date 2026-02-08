"""Format and persist scan findings to Snowflake tables."""

import json
import uuid
from typing import List

from bouncer_logic import config


def format_finding(
    scan_id: str,
    repo_id: int,
    file_path: str,
    raw_finding: dict,
    model_used: str,
    raw_response: dict,
    blame_info: dict = None,
) -> dict:
    """Convert a raw AI finding into a row matching SCAN_RESULTS."""
    # Truncate fields to fit Snowflake column limits
    def truncate(s: str, max_len: int = 4000) -> str:
        if s and len(s) > max_len:
            return s[:max_len - 3] + "..."
        return s or ""
    
    return {
        "FINDING_ID": str(uuid.uuid4()),
        "SCAN_ID": scan_id,
        "REPO_ID": repo_id,
        "FILE_PATH": truncate(file_path, 1000),
        "LINE_NUMBER": raw_finding.get("line_number"),
        "SEVERITY": raw_finding["severity"],
        "VULN_TYPE": truncate(raw_finding["vuln_type"], 128),
        "DESCRIPTION": truncate(raw_finding["description"], 4000),
        "FIX_SUGGESTION": truncate(raw_finding.get("fix_suggestion", ""), 4000),
        "CODE_SNIPPET": truncate(raw_finding.get("code_snippet", ""), 4000),
        "MODEL_USED": model_used,
        "CONFIDENCE": raw_finding.get("confidence", 0.0),
        "COMMIT_HASH": blame_info["hash"] if blame_info else None,
        "COMMIT_AUTHOR": blame_info["author"] if blame_info else None,
        "COMMIT_DATE": blame_info["date"] if blame_info else None,
    }


def persist_findings(conn, findings: List[dict]) -> int:
    """Insert findings into SCAN_RESULTS. Returns inserted row count."""
    if not findings:
        return 0

    cur = conn.cursor()
    try:
        cur.executemany(
            f"""INSERT INTO {config.TABLE_SCAN_RESULTS}
                (FINDING_ID, SCAN_ID, REPO_ID, FILE_PATH, LINE_NUMBER,
                 SEVERITY, VULN_TYPE, DESCRIPTION, FIX_SUGGESTION,
                 CODE_SNIPPET, MODEL_USED, CONFIDENCE,
                 COMMIT_HASH, COMMIT_AUTHOR, COMMIT_DATE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    f["FINDING_ID"], f["SCAN_ID"], f["REPO_ID"],
                    f["FILE_PATH"], f["LINE_NUMBER"],
                    f["SEVERITY"], f["VULN_TYPE"], f["DESCRIPTION"],
                    f["FIX_SUGGESTION"], f["CODE_SNIPPET"],
                    f["MODEL_USED"], f["CONFIDENCE"],
                    f["COMMIT_HASH"], f["COMMIT_AUTHOR"], f["COMMIT_DATE"],
                )
                for f in findings
            ],
        )
        return len(findings)
    finally:
        cur.close()


def update_scan_status(
    conn,
    scan_id: str,
    status: str,
    files_scanned: int = 0,
    findings_count: int = 0,
    error_message: str = None,
) -> None:
    """Update a SCAN_HISTORY row with parameterized SQL."""
    cur = conn.cursor()
    try:
        # Truncate error_message to fit column limit
        if error_message and len(error_message) > 500:
            error_message = error_message[:497] + "..."
            
        if error_message:
            cur.execute(
                """UPDATE CODEBOUNCER.CORE.SCAN_HISTORY
                   SET STATUS = %s, FILES_SCANNED = %s, FINDINGS_COUNT = %s,
                       COMPLETED_AT = CURRENT_TIMESTAMP(), ERROR_MESSAGE = %s
                   WHERE SCAN_ID = %s""",
                (status, files_scanned, findings_count, error_message, scan_id),
            )
        else:
            cur.execute(
                """UPDATE CODEBOUNCER.CORE.SCAN_HISTORY
                   SET STATUS = %s, FILES_SCANNED = %s, FINDINGS_COUNT = %s,
                       COMPLETED_AT = CURRENT_TIMESTAMP()
                   WHERE SCAN_ID = %s""",
                (status, files_scanned, findings_count, scan_id),
            )
    finally:
        cur.close()
