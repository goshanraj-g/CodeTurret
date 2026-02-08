"""Tests for bouncer_logic.git_intel."""

import json
import os
import subprocess

import pytest

from bouncer_logic import git_intel


@pytest.fixture
def git_repo(tmp_path):
    """Create a small git repo with several commits for testing."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )

    # Commit 1: add app.py
    (tmp_path / "app.py").write_text("print('hello')")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )

    # Commit 2: modify app.py
    (tmp_path / "app.py").write_text("print('world')")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "update app"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )

    # Commit 3: add auth.py with security fix message
    (tmp_path / "auth.py").write_text("def login(): pass")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fix auth bypass vulnerability"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )

    # Commit 4: modify app.py again
    (tmp_path / "app.py").write_text("print('updated')")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "refactor app"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )

    return tmp_path


class TestGetHotFiles:
    def test_counts_file_changes(self, git_repo):
        hot = git_intel.get_hot_files(str(git_repo))
        # app.py modified in 3 commits (initial, update, refactor)
        assert hot.get("app.py", 0) >= 3
        # auth.py modified in 1 commit
        assert hot.get("auth.py", 0) >= 1

    def test_empty_repo(self, tmp_path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
        hot = git_intel.get_hot_files(str(tmp_path))
        assert hot == {}


class TestGetSecurityCommits:
    def test_finds_security_related_files(self, git_repo):
        sec = git_intel.get_security_commits(str(git_repo))
        # auth.py was touched in "fix auth bypass vulnerability"
        assert "auth.py" in sec
        assert any("fix" in msg.lower() for msg in sec["auth.py"])

    def test_excludes_non_security_files(self, git_repo):
        sec = git_intel.get_security_commits(str(git_repo))
        # app.py was only touched in "initial commit", "update app", "refactor app"
        # None of those match security keywords
        assert "app.py" not in sec


class TestGetRepoContext:
    def test_reads_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("# My Project\n\nA cool web app.")
        ctx = git_intel.get_repo_context(str(tmp_path))
        assert "My Project" in ctx

    def test_reads_package_json(self, tmp_path):
        pkg = {"description": "A web app", "dependencies": {"express": "^4.0", "pg": "^8.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        ctx = git_intel.get_repo_context(str(tmp_path))
        assert "express" in ctx
        assert "A web app" in ctx

    def test_empty_dir_returns_empty(self, tmp_path):
        ctx = git_intel.get_repo_context(str(tmp_path))
        assert ctx == ""
