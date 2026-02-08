"""Pre-scan file risk scoring to prioritize security-relevant files."""

import os
import re
from typing import Dict, List, Set

from bouncer_logic import config


# -- Risk classification rules -----------------------------------------------

# Filenames / paths that are inherently high-risk
HIGH_RISK_NAMES = {
    ".env", ".env.local", ".env.production",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "secrets.json", "credentials.json",
}

HIGH_RISK_PATH_PATTERNS = {
    re.compile(r"\.github/workflows/"),   # CI/CD configs
    re.compile(r"(^|/)auth"),             # auth modules
    re.compile(r"(^|/)login"),
    re.compile(r"(^|/)middleware"),
    re.compile(r"(^|/)api/"),
    re.compile(r"(^|/)routes?/"),
    re.compile(r"(^|/)controllers?/"),
    re.compile(r"(^|/)handlers?/"),
    re.compile(r"(^|/)db/"),
    re.compile(r"(^|/)models?/"),
    re.compile(r"(^|/)config"),
}

# Keywords inside file content that signal risk
RISK_KEYWORDS = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "access_key", "credentials",
    "eval(", "exec(", "subprocess", "os.system", "child_process",
    "innerHTML", "dangerouslySetInnerHTML",
    "SELECT ", "INSERT ", "UPDATE ", "DELETE ",
    "pickle.loads", "yaml.load",
    "verify=False", "ssl=False",
}

# Files to always skip (never security-relevant)
SKIP_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "changelog.md", "license.md", "license", "license.txt",
    "contributing.md", ".prettierrc", ".eslintrc",
}

SKIP_PATH_PATTERNS = {
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)\.git/"),
    re.compile(r"(^|/)dist/"),
    re.compile(r"(^|/)build/"),
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"(^|/)vendor/"),
}

SKIP_EXTENSIONS = {
    ".md", ".txt", ".rst", ".csv", ".svg", ".png", ".jpg", ".gif",
    ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map",
}

# Multi-dot suffixes that os.path.splitext won't catch
SKIP_SUFFIXES = (".d.ts", ".min.js", ".min.css")

# Risk score values
RISK_HIGH = 3
RISK_MEDIUM = 2
RISK_LOW = 1
RISK_SKIP = 0


def assess_file_risk(file_path: str, content: str = "") -> int:
    """Score a file's security risk (0 = skip, 1 = low, 2 = medium, 3 = high).

    Scoring is based on filename, path, and optional content keywords.
    """
    lower_path = file_path.lower()
    basename = os.path.basename(lower_path)
    _, ext = os.path.splitext(basename)

    # Skip rules
    if basename in SKIP_NAMES:
        return RISK_SKIP
    if ext in SKIP_EXTENSIONS:
        return RISK_SKIP
    if any(lower_path.endswith(s) for s in SKIP_SUFFIXES):
        return RISK_SKIP
    if any(p.search(lower_path) for p in SKIP_PATH_PATTERNS):
        return RISK_SKIP

    score = RISK_LOW

    # High-risk filename
    if basename in HIGH_RISK_NAMES:
        return RISK_HIGH

    # High-risk path pattern
    if any(p.search(lower_path) for p in HIGH_RISK_PATH_PATTERNS):
        score = max(score, RISK_HIGH)

    # Content-based keyword scan (cheap string search, not AI)
    if content:
        lower_content = content.lower()
        matches = sum(1 for kw in RISK_KEYWORDS if kw.lower() in lower_content)
        if matches >= 3:
            score = max(score, RISK_HIGH)
        elif matches >= 1:
            score = max(score, RISK_MEDIUM)

    return score


def apply_git_signals(
    files: List[Dict],
    hot_files: Dict[str, int],
    security_files: Dict[str, List[str]],
) -> List[Dict]:
    """Boost risk_score based on git history signals.

    - Files changed >= GIT_HOT_FILE_THRESHOLD times: +GIT_HOT_FILE_BONUS
    - Files touched by security-relevant commits: +GIT_SECURITY_COMMIT_BONUS
    """
    for f in files:
        path = f["path"]
        if hot_files.get(path, 0) >= config.GIT_HOT_FILE_THRESHOLD:
            f["risk_score"] = f.get("risk_score", 0) + config.GIT_HOT_FILE_BONUS
        if path in security_files:
            f["risk_score"] = f.get("risk_score", 0) + config.GIT_SECURITY_COMMIT_BONUS
    return files


def prioritize_files(
    files: List[Dict[str, str]],
    contents: Dict[str, str] = None,
    hot_files: Dict[str, int] = None,
    security_files: Dict[str, List[str]] = None,
    max_files: int = None,
) -> List[Dict[str, str]]:
    """Sort files by risk score (highest first) and remove skippable files.

    ``files`` is a list of dicts with at least a ``path`` key.
    ``contents`` is an optional mapping of path → file content for
    keyword-based scoring.  When omitted, scoring uses path only.
    ``hot_files`` and ``security_files`` are optional git intel signals.
    ``max_files`` caps the number of files returned.

    Returns filtered and sorted list with a ``risk_score`` key added.
    """
    contents = contents or {}
    scored: List[Dict[str, str]] = []

    for f in files:
        path = f["path"]
        content = contents.get(path, "")
        risk = assess_file_risk(path, content)
        if risk == RISK_SKIP:
            continue
        scored.append({**f, "risk_score": risk})

    # Apply git history signals if provided
    if hot_files or security_files:
        apply_git_signals(scored, hot_files or {}, security_files or {})

    scored.sort(key=lambda x: x["risk_score"], reverse=True)

    if max_files is not None:
        scored = scored[:max_files]

    return scored
