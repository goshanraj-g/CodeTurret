"""Main scan orchestrator. Clones a repo locally, scans with Gemini AI.

Scanning: Gemini API (flash triage + pro deep analysis)
Storage & Analytics: Snowflake (persist findings + Cortex post-scan insights)
"""

import logging
import uuid
from typing import Optional

from bouncer_logic import (
    code_extractor,
    config,
    cortex_client,
    gemini_client,
    git_intel,
    github_client,
    result_formatter,
    risk_assessor,
)

logger = logging.getLogger(__name__)


def run_security_scan(
    repo_url: str,
    repo_name: Optional[str] = None,
    deep_scan: bool = False,
) -> dict:
    """Scan a GitHub repository for security vulnerabilities.

    1. Clone repo with git history.
    2. Gather git intelligence (hot files, security commits, repo context).
    3. Walk files, score risk with git signals, cap at MAX_SCAN_FILES.
    4. Extract security-relevant snippets instead of full files.
    5. Two-pass Gemini scan with enriched prompts.
    6. Persist findings to Snowflake.
    7. Generate post-scan analytics via Snowflake Cortex.
    8. Cleanup cloned repo.
    """
    repo_name = repo_name or repo_url.rstrip("/").split("/")[-1]
    conn = config.get_snowflake_connection()

    summary = {
        "repo": repo_name,
        "total_files": 0,
        "total_findings": 0,
        "skipped_files": 0,
        "errors": [],
        "insights": None,
    }

    scan_id = str(uuid.uuid4())
    repo_dir = None

    try:
        # Get or create repo config in Snowflake
        repo_id = _ensure_repo_config(conn, repo_name, repo_url)

        # Create scan record
        _create_scan_record(conn, scan_id, repo_id)

        # Clone repo with history for git intel
        logger.info("Cloning %s ...", repo_url)
        repo_dir = github_client.clone_repo(
            repo_url, depth=config.GIT_CLONE_DEPTH
        )

        # Gather git intelligence
        logger.info("Analyzing git history ...")
        hot_files = git_intel.get_hot_files(repo_dir, config.GIT_MAX_COMMITS)
        security_files = git_intel.get_security_commits(repo_dir, config.GIT_MAX_COMMITS)
        repo_context = git_intel.get_repo_context(repo_dir)

        # List and read files
        raw_files = github_client.list_repo_files(repo_dir)
        contents: dict[str, str] = {}
        for file_info in raw_files:
            content = github_client.read_file_content(file_info["full_path"])
            contents[file_info["path"]] = content

        # Git-boosted risk scoring, prioritization, and file cap
        files = risk_assessor.prioritize_files(
            raw_files, contents,
            hot_files=hot_files,
            security_files=security_files,
            max_files=config.MAX_SCAN_FILES,
        )
        summary["skipped_files"] = len(raw_files) - len(files)

        logger.info(
            "Scanning %d files (skipped %d) ...",
            len(files), summary["skipped_files"],
        )

        all_findings: list[dict] = []

        for file_info in files:
            path = file_info["path"]
            full_content = contents[path]

            # Extract security-relevant snippets
            snippets = code_extractor.extract_security_snippets(full_content, path)
            focused_content = code_extractor.build_focused_content(snippets, path)

            # Use focused content if snippets found, otherwise full content
            scan_content = focused_content if focused_content else full_content

            # Build git context for this file
            git_context = _build_git_context(path, hot_files, security_files)

            # Pass 1 — Gemini Flash triage
            triage_result = gemini_client.triage_with_flash(
                scan_content, path,
                repo_context=repo_context,
                git_context=git_context,
            )
            findings_for_file = triage_result.get("findings", [])
            model_used = config.MODEL_FLASH

            # Pass 2 — Gemini Pro deep analysis when warranted
            needs_deep = deep_scan or any(
                f.get("confidence", 1.0) < config.DEEP_SCAN_THRESHOLD
                or f.get("severity") in ("CRITICAL", "HIGH")
                for f in findings_for_file
            )

            if needs_deep and findings_for_file:
                deep_result = gemini_client.deep_analyze_with_pro(
                    scan_content, path, findings_for_file,
                    repo_context=repo_context,
                    git_context=git_context,
                )
                if deep_result is not None:
                    findings_for_file = deep_result.get("findings", [])
                    model_used = config.MODEL_PRO
                else:
                    logger.info(
                        "Keeping flash results for %s (pro unavailable)", path
                    )

            for raw in findings_for_file:
                formatted = result_formatter.format_finding(
                    scan_id,
                    repo_id,
                    path,
                    raw,
                    model_used,
                    triage_result if model_used == config.MODEL_FLASH else deep_result,
                )
                all_findings.append(formatted)

        count = result_formatter.persist_findings(conn, all_findings)

        result_formatter.update_scan_status(
            conn, scan_id, "COMPLETED",
            files_scanned=len(files),
            findings_count=count,
        )
        summary["total_files"] = len(files)
        summary["total_findings"] = count

        # Post-scan: generate Cortex analytics insights
        if count > 0:
            try:
                insights = cortex_client.get_scan_insights(conn, scan_id)
                summary["insights"] = insights
                logger.info("Cortex insights generated for scan %s", scan_id)
            except Exception as exc:
                logger.warning("Cortex insights failed (non-fatal): %s", exc)

    except Exception as exc:
        logger.exception("Scan failed for %s", repo_url)
        result_formatter.update_scan_status(
            conn, scan_id, "FAILED", error_message=str(exc)
        )
        summary["errors"].append({"repo": repo_name, "error": str(exc)})

    finally:
        if repo_dir:
            github_client.cleanup_repo(repo_dir)
        conn.close()

    return summary


# -- helpers -----------------------------------------------------------------

def _build_git_context(
    path: str,
    hot_files: dict[str, int],
    security_files: dict[str, list[str]],
) -> str:
    """Build a human-readable git context string for a file."""
    parts: list[str] = []
    change_count = hot_files.get(path, 0)
    if change_count:
        parts.append(f"Modified {change_count} times in recent history")
    sec_commits = security_files.get(path, [])
    if sec_commits:
        msgs = sec_commits[:3]
        parts.append(f"Security-related commits: {'; '.join(msgs)}")
    return ". ".join(parts)


def _ensure_repo_config(conn, repo_name: str, repo_url: str) -> int:
    """Get existing repo ID or create a new config row. Returns REPO_ID."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT REPO_ID FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG WHERE REPO_NAME = %s",
            (repo_name,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """INSERT INTO CODEBOUNCER.CORE.REPOSITORY_CONFIG
               (REPO_NAME, REPO_URL, GIT_REPO_NAME, DEFAULT_BRANCH)
               VALUES (%s, %s, %s, 'main')""",
            (repo_name, repo_url, repo_name),
        )
        cur.execute("SELECT MAX(REPO_ID) FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG")
        return cur.fetchone()[0]
    finally:
        cur.close()


def _create_scan_record(conn, scan_id: str, repo_id: int) -> None:
    """Insert a new SCAN_HISTORY row."""
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO CODEBOUNCER.CORE.SCAN_HISTORY
               (SCAN_ID, REPO_ID, STATUS, SCAN_TYPE, STARTED_AT)
               VALUES (%s, %s, 'RUNNING', 'FULL', CURRENT_TIMESTAMP())""",
            (scan_id, repo_id),
        )
    finally:
        cur.close()
