"""Read files from Snowflake Git Integration stages."""

import os
from typing import Dict, List, Set

from snowflake.snowpark import Session


def list_files_in_repo(
    session: Session,
    git_repo_stage: str,
    branch: str,
    extensions: Set[str],
) -> List[Dict[str, str]]:
    """List scannable files in a git repo branch.

    Returns a list of dicts with ``path`` (relative) and
    ``full_stage_path`` (stage-qualified) keys.
    """
    stage_path = f"{git_repo_stage}/branches/{branch}"
    rows = session.sql("LS ?", params=[stage_path]).collect()

    results: List[Dict[str, str]] = []
    for row in rows:
        name = row["name"]
        _, ext = os.path.splitext(name)
        if ext in extensions:
            relative = name.replace(f"{stage_path}/", "", 1)
            results.append(
                {"path": relative, "full_stage_path": name}
            )
    return results


def read_file_content(session: Session, stage_file_path: str) -> str:
    """Read raw text content of a single file from a git stage."""
    result = session.sql(
        (
            "SELECT $1 FROM ? "
            "(FILE_FORMAT => (TYPE='CSV', FIELD_DELIMITER='NONE', "
            "RECORD_DELIMITER='NONE', ESCAPE='NONE'))"
        ),
        params=[stage_file_path],
    ).collect()
    return result[0][0] if result else ""


def get_changed_files(
    session: Session,
    git_repo_stage: str,
    current_ref: str,
    previous_ref: str,
    extensions: Set[str],
) -> List[Dict[str, str]]:
    """Return files that differ between two refs.

    Snowflake git integration doesn't expose ``git diff``, so we
    compare file listings from two commit/tag refs.  Files present
    only in the current ref or whose stage sizes differ are treated
    as changed.
    """
    current_files = _list_at_ref(session, git_repo_stage, current_ref, extensions)
    previous_files = _list_at_ref(session, git_repo_stage, previous_ref, extensions)

    prev_map = {f["path"]: f.get("size") for f in previous_files}
    changed: List[Dict[str, str]] = []
    for f in current_files:
        if f["path"] not in prev_map or prev_map[f["path"]] != f.get("size"):
            changed.append(f)
    return changed


# -- helpers -----------------------------------------------------------------

def _list_at_ref(
    session: Session,
    git_repo_stage: str,
    ref: str,
    extensions: Set[str],
) -> List[Dict[str, str]]:
    """List files under a specific commit or tag ref."""
    stage_path = f"{git_repo_stage}/commits/{ref}"
    rows = session.sql("LS ?", params=[stage_path]).collect()

    results: List[Dict[str, str]] = []
    for row in rows:
        name = row["name"]
        _, ext = os.path.splitext(name)
        if ext in extensions:
            relative = name.replace(f"{stage_path}/", "", 1)
            results.append(
                {
                    "path": relative,
                    "full_stage_path": name,
                    "size": row.get("size"),
                }
            )
    return results
