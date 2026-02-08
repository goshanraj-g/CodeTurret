"""Clone GitHub repos and walk local files."""

import os
import shutil
import subprocess
import tempfile
from typing import List, Dict, Optional, Set

from bouncer_logic import config


def clone_repo(repo_url: str, target_dir: Optional[str] = None, depth: int = 1) -> str:
    """Clone a repo and return the local directory path."""
    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix="codebouncer_")

    subprocess.run(
        ["git", "clone", "--depth", str(depth), repo_url, target_dir],
        check=True,
        capture_output=True,
        text=True,
    )
    return target_dir


def list_repo_files(
    repo_dir: str,
    extensions: Optional[Set[str]] = None,
) -> List[Dict[str, str]]:
    """Walk the repo directory and return files matching extensions.

    Returns list of dicts with ``path`` (relative) and ``full_path`` (absolute).
    """
    extensions = extensions or config.SCANNABLE_EXTENSIONS
    files: List[Dict[str, str]] = []

    for root, dirs, filenames in os.walk(repo_dir):
        # Skip hidden dirs and common non-source dirs
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in {"node_modules", "__pycache__", "dist", "build", "vendor"}
        ]
        for name in filenames:
            _, ext = os.path.splitext(name)
            if ext in extensions:
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, repo_dir).replace("\\", "/")
                files.append({"path": rel_path, "full_path": full_path})

    return files


def read_file_content(file_path: str, max_size: int = config.MAX_FILE_SIZE) -> str:
    """Read a file's content, truncating if it exceeds max_size."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(max_size)
    return content


def cleanup_repo(repo_dir: str) -> None:
    """Remove a cloned repo directory."""
    shutil.rmtree(repo_dir, ignore_errors=True)
