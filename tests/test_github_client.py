"""Tests for bouncer_logic.github_client."""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from bouncer_logic import github_client


class TestCloneRepo:
    @patch("bouncer_logic.github_client.subprocess.run")
    def test_calls_git_clone(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        target = tempfile.mkdtemp()

        github_client.clone_repo("https://github.com/user/repo", target)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "git" in args
        assert "clone" in args
        assert "--depth" in args
        assert "https://github.com/user/repo" in args

    @patch("bouncer_logic.github_client.subprocess.run")
    def test_creates_temp_dir_if_none(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = github_client.clone_repo("https://github.com/user/repo")

        assert result is not None
        assert os.path.isdir(result)
        os.rmdir(result)

    @patch("bouncer_logic.github_client.subprocess.run")
    def test_raises_on_clone_failure(self, mock_run):
        mock_run.side_effect = Exception("clone failed")

        with pytest.raises(Exception, match="clone failed"):
            github_client.clone_repo("https://github.com/bad/repo")


class TestListRepoFiles:
    def test_finds_python_files(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "style.css").write_text("body {}")
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "utils.py").write_text("y = 2")

        result = github_client.list_repo_files(str(tmp_path), {".py"})

        paths = [f["path"] for f in result]
        assert "app.py" in paths
        assert "src/utils.py" in paths
        assert not any("css" in p for p in paths)

    def test_skips_hidden_dirs(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.py").write_text("secret")
        (tmp_path / "app.py").write_text("x = 1")

        result = github_client.list_repo_files(str(tmp_path), {".py"})

        paths = [f["path"] for f in result]
        assert "app.py" in paths
        assert not any(".git" in p for p in paths)

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "lodash"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")
        (tmp_path / "app.js").write_text("console.log('hi')")

        result = github_client.list_repo_files(str(tmp_path), {".js"})

        paths = [f["path"] for f in result]
        assert "app.js" in paths
        assert not any("node_modules" in p for p in paths)

    def test_empty_directory(self, tmp_path):
        result = github_client.list_repo_files(str(tmp_path), {".py"})
        assert result == []

    def test_uses_default_extensions(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "app.ts").write_text("const x = 1")
        (tmp_path / "data.csv").write_text("a,b")

        result = github_client.list_repo_files(str(tmp_path))

        paths = [f["path"] for f in result]
        assert "app.py" in paths
        assert "app.ts" in paths
        assert "data.csv" not in paths


class TestReadFileContent:
    def test_reads_content(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")

        content = github_client.read_file_content(str(f))
        assert content == "print('hello')"

    def test_truncates_large_files(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("x" * 100)

        content = github_client.read_file_content(str(f), max_size=10)
        assert len(content) == 10


class TestCleanupRepo:
    def test_removes_directory(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        (target / "file.txt").write_text("data")

        github_client.cleanup_repo(str(target))

        assert not target.exists()

    def test_handles_nonexistent_dir(self):
        github_client.cleanup_repo("/nonexistent/path/12345")
