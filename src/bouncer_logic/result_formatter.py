"""Format and persist scan findings to Snowflake tables."""

import json
import uuid
from typing import List

from snowflake.snowpark import Session

from bouncer_logic import config


def format_finding(
    scan_id: str,
    repo_id: int,
    file_path: str,
    raw_finding: dict,
    model_used: str,
    raw_response: dict,
) -> dict:
    """Convert a raw AI finding into a row matching SCAN_RESULTS."""
    return {
        "FINDING_ID": str(uuid.uuid4()),
        "SCAN_ID": scan_id,
        "REPO_ID": repo_id,
        "FILE_PATH": file_path,
        "LINE_NUMBER": raw_finding.get("line_number"),
        "SEVERITY": raw_finding["severity"],
        "VULN_TYPE": raw_finding["vuln_type"],
        "DESCRIPTION": raw_finding["description"],
        "FIX_SUGGESTION": raw_finding.get("fix_suggestion", ""),
        "CODE_SNIPPET": raw_finding.get("code_snippet", ""),
        "MODEL_USED": model_used,
        "CONFIDENCE": raw_finding.get("confidence", 0.0),
        "RAW_RESPONSE": json.dumps(raw_response),
    }


def persist_findings(session: Session, findings: List[dict]) -> int:
    """Insert findings into SCAN_RESULTS. Returns inserted row count."""
    if not findings:
        return 0

    df = session.create_dataframe(findings)
    df.write.mode("append").save_as_table(config.TABLE_SCAN_RESULTS)
    return len(findings)


def update_scan_status(
    session: Session,
    scan_id: str,
    status: str,
    files_scanned: int = 0,
    findings_count: int = 0,
    error_message: str = None,
) -> None:
    """Update a SCAN_HISTORY row with parameterized SQL."""
    if error_message:
        session.sql(
            """UPDATE CODEBOUNCER.CORE.SCAN_HISTORY
               SET STATUS = ?, FILES_SCANNED = ?, FINDINGS_COUNT = ?,
                   COMPLETED_AT = CURRENT_TIMESTAMP(), ERROR_MESSAGE = ?
               WHERE SCAN_ID = ?""",
            params=[status, files_scanned, findings_count, error_message, scan_id],
        ).collect()
    else:
        session.sql(
            """UPDATE CODEBOUNCER.CORE.SCAN_HISTORY
               SET STATUS = ?, FILES_SCANNED = ?, FINDINGS_COUNT = ?,
                   COMPLETED_AT = CURRENT_TIMESTAMP()
               WHERE SCAN_ID = ?""",
            params=[status, files_scanned, findings_count, scan_id],
        ).collect()
