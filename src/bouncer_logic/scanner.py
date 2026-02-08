"""Main scan orchestrator. Entry point for the RUN_SECURITY_SCAN stored procedure."""

import uuid
from typing import Optional

from snowflake.snowpark import Session

from bouncer_logic import config, cortex_client, file_reader, result_formatter


def run_security_scan(
    session: Session,
    repo_name: Optional[str] = None,
    scan_type: str = "INCREMENTAL",
) -> dict:
    """Scan repositories for security vulnerabilities.

    This is the handler called by the ``RUN_SECURITY_SCAN`` stored procedure.

    Algorithm
    ---------
    1. Load active repo configs.
    2. For each repo:
       a. Create a SCAN_HISTORY record (RUNNING).
       b. List files to scan.
       c. Two-pass scan per file (flash triage → optional pro deep analysis).
       d. Persist findings and update history.
    3. Return summary dict.
    """
    summary = {
        "repos_scanned": 0,
        "total_files": 0,
        "total_findings": 0,
        "errors": [],
    }

    repos = _get_repo_configs(session, repo_name)

    for repo in repos:
        scan_id = str(uuid.uuid4())
        try:
            _create_scan_record(session, scan_id, repo)

            git_stage = (
                f"@CODEBOUNCER.INTEGRATIONS.{repo['GIT_REPO_NAME']}"
            )
            extensions = set(
                repo.get("FILE_EXTENSIONS", config.SCANNABLE_EXTENSIONS)
            )
            files = file_reader.list_files_in_repo(
                session, git_stage, repo["DEFAULT_BRANCH"], extensions
            )

            all_findings: list[dict] = []

            for file_info in files:
                content = file_reader.read_file_content(
                    session, file_info["full_stage_path"]
                )
                if len(content) > config.MAX_FILE_SIZE:
                    content = content[: config.MAX_FILE_SIZE]

                # Pass 1 — flash triage
                triage_result = cortex_client.triage_with_flash(
                    session, content, file_info["path"]
                )
                findings_for_file = triage_result.get("findings", [])
                model_used = config.MODEL_FLASH

                # Pass 2 — pro deep analysis when warranted
                needs_deep = repo.get("DEEP_SCAN", False) or any(
                    f.get("confidence", 1.0) < config.DEEP_SCAN_THRESHOLD
                    or f.get("severity") in ("CRITICAL", "HIGH")
                    for f in findings_for_file
                )

                if needs_deep and findings_for_file:
                    deep_result = cortex_client.deep_analyze_with_pro(
                        session, content, file_info["path"], findings_for_file
                    )
                    findings_for_file = deep_result.get("findings", [])
                    model_used = config.MODEL_PRO

                for raw in findings_for_file:
                    formatted = result_formatter.format_finding(
                        scan_id,
                        repo["REPO_ID"],
                        file_info["path"],
                        raw,
                        model_used,
                        triage_result if model_used == config.MODEL_FLASH else deep_result,
                    )
                    all_findings.append(formatted)

            count = result_formatter.persist_findings(session, all_findings)

            result_formatter.update_scan_status(
                session,
                scan_id,
                "COMPLETED",
                files_scanned=len(files),
                findings_count=count,
            )
            summary["repos_scanned"] += 1
            summary["total_files"] += len(files)
            summary["total_findings"] += count

        except Exception as exc:
            result_formatter.update_scan_status(
                session, scan_id, "FAILED", error_message=str(exc)
            )
            summary["errors"].append(
                {"repo": repo.get("REPO_NAME", "unknown"), "error": str(exc)}
            )

    return summary


# -- helpers -----------------------------------------------------------------

def _get_repo_configs(session: Session, repo_name: Optional[str]) -> list:
    """Fetch active repository configurations."""
    if repo_name:
        rows = session.sql(
            "SELECT * FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG "
            "WHERE REPO_NAME = ? AND IS_ACTIVE = TRUE",
            params=[repo_name],
        ).collect()
    else:
        rows = session.sql(
            "SELECT * FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG WHERE IS_ACTIVE = TRUE"
        ).collect()
    return [row.as_dict() for row in rows]


def _create_scan_record(session: Session, scan_id: str, repo: dict) -> None:
    """Insert a new SCAN_HISTORY row."""
    session.sql(
        """INSERT INTO CODEBOUNCER.CORE.SCAN_HISTORY
           (SCAN_ID, REPO_ID, BRANCH, STATUS, SCAN_TYPE, STARTED_AT)
           VALUES (?, ?, ?, 'RUNNING', 'INCREMENTAL', CURRENT_TIMESTAMP())""",
        params=[scan_id, repo["REPO_ID"], repo["DEFAULT_BRANCH"]],
    ).collect()
