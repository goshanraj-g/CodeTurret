"""Extract git history signals for smarter file prioritization."""

import json
import os
import re
import subprocess
from collections import defaultdict
from typing import Dict, List, Optional

SECURITY_KEYWORDS = re.compile(
    r"\b(fix|bug|vuln|security|auth|inject|xss|csrf|patch|cve|sanitize|escape|validate|exploit|bypass)\b",
    re.IGNORECASE,
)


def get_hot_files(repo_dir: str, max_count: int = 50) -> Dict[str, int]:
    """Count how many times each file was changed in the last N commits.

    Returns ``{relative_path: change_count}``.
    """
    result = subprocess.run(
        ["git", "log", f"--max-count={max_count}", "--name-only", "--pretty=format:"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    counts: Dict[str, int] = defaultdict(int)
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            counts[line] += 1
    return dict(counts)


def get_security_commits(repo_dir: str, max_count: int = 50) -> Dict[str, List[str]]:
    """Find files touched by commits whose messages match security keywords.

    Returns ``{relative_path: [matching_commit_messages]}``.
    """
    # Get commits with messages and changed files
    result = subprocess.run(
        [
            "git", "log", f"--max-count={max_count}",
            "--pretty=format:__COMMIT__%s",
            "--name-only",
        ],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )

    mapping: Dict[str, List[str]] = defaultdict(list)
    current_message: Optional[str] = None
    is_security = False

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("__COMMIT__"):
            current_message = line[len("__COMMIT__"):]
            is_security = bool(SECURITY_KEYWORDS.search(current_message))
        elif line and is_security and current_message:
            mapping[line].append(current_message)

    return dict(mapping)


def blame_line(
    repo_dir: str, file_path: str, line_number: int
) -> Optional[Dict[str, str]]:
    """Get the commit that last modified a specific line via git blame.

    Returns ``{"hash": "abc123f", "author": "Name", "date": "2025-12-01"}``
    or ``None`` if blame fails (file missing, line out of range, shallow clone).
    """
    if not line_number or line_number < 1:
        return None

    try:
        result = subprocess.run(
            [
                "git", "blame", "-L", f"{line_number},{line_number}",
                "--porcelain", "--", file_path,
            ],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.splitlines()
        if not lines:
            return None

        # First line: <hash> <orig_line> <final_line> <num_lines>
        commit_hash = lines[0].split()[0]

        author = ""
        author_time = ""
        for line in lines[1:]:
            if line.startswith("author "):
                author = line[len("author "):]
            elif line.startswith("author-time "):
                author_time = line[len("author-time "):]

        # Convert unix timestamp to ISO date
        date_str = ""
        if author_time:
            from datetime import datetime, timezone
            ts = int(author_time)
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

        return {
            "hash": commit_hash,
            "author": author,
            "date": date_str,
        }
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def get_repo_context(repo_dir: str) -> str:
    """Build a short project description from README and package metadata.

    Returns a plain-text summary string (or empty string if nothing found).
    """
    parts: List[str] = []

    # Try README
    for name in ("README.md", "README.rst", "README.txt", "README"):
        readme_path = os.path.join(repo_dir, name)
        if os.path.isfile(readme_path):
            with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(2000).strip()
            if text:
                # Take the first paragraph / heading block
                first_block = text.split("\n\n")[0]
                parts.append(first_block)
            break

    # Try package.json for deps
    pkg_path = os.path.join(repo_dir, "package.json")
    if os.path.isfile(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            desc = pkg.get("description", "")
            if desc:
                parts.append(f"Description: {desc}")
            deps = list(pkg.get("dependencies", {}).keys())[:15]
            if deps:
                parts.append(f"Dependencies: {', '.join(deps)}")
        except (json.JSONDecodeError, OSError):
            pass

    # Try pyproject.toml / setup.py for Python projects
    pyproject_path = os.path.join(repo_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read(2000)
            parts.append("Python project (pyproject.toml found)")
        except OSError:
            pass

    return "\n".join(parts) if parts else ""
