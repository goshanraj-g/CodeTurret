"""Tests for bouncer_logic.file_reader."""

from unittest.mock import MagicMock

from bouncer_logic import file_reader


class TestListFilesInRepo:
    def test_filters_by_extension(self, mock_session):
        mock_session.sql.return_value.collect.return_value = [
            {"name": "@repo/branches/main/src/app.py", "size": 100},
            {"name": "@repo/branches/main/src/style.css", "size": 50},
            {"name": "@repo/branches/main/src/index.js", "size": 200},
        ]

        result = file_reader.list_files_in_repo(
            mock_session, "@repo", "main", {".py", ".js"}
        )

        paths = [f["path"] for f in result]
        assert "src/app.py" in paths
        assert "src/index.js" in paths
        assert all("css" not in p for p in paths)

    def test_empty_repo(self, mock_session):
        mock_session.sql.return_value.collect.return_value = []
        result = file_reader.list_files_in_repo(
            mock_session, "@repo", "main", {".py"}
        )
        assert result == []

    def test_builds_correct_stage_path(self, mock_session):
        mock_session.sql.return_value.collect.return_value = []
        file_reader.list_files_in_repo(
            mock_session, "@myrepo", "develop", {".py"}
        )

        sql_call = mock_session.sql.call_args
        params = sql_call.kwargs.get("params", sql_call.args[1] if len(sql_call.args) > 1 else [])
        assert any("@myrepo/branches/develop" in str(p) for p in params)


class TestReadFileContent:
    def test_returns_content(self, mock_session):
        mock_session.sql.return_value.collect.return_value = [
            ("print('hello')",)
        ]
        content = file_reader.read_file_content(mock_session, "@repo/f.py")
        assert content == "print('hello')"

    def test_empty_file(self, mock_session):
        mock_session.sql.return_value.collect.return_value = []
        content = file_reader.read_file_content(mock_session, "@repo/empty.py")
        assert content == ""


class TestGetChangedFiles:
    def test_detects_new_file(self, mock_session):
        call_count = [0]
        def side_effect(*args, **kwargs):
            mock = MagicMock()
            if call_count[0] == 0:
                # current commit
                mock.collect.return_value = [
                    {"name": "@repo/commits/abc/a.py", "size": 100},
                    {"name": "@repo/commits/abc/b.py", "size": 200},
                ]
            else:
                # previous commit
                mock.collect.return_value = [
                    {"name": "@repo/commits/def/a.py", "size": 100},
                ]
            call_count[0] += 1
            return mock

        mock_session.sql.side_effect = side_effect

        changed = file_reader.get_changed_files(
            mock_session, "@repo", "abc", "def", {".py"}
        )
        paths = [f["path"] for f in changed]
        assert "b.py" in paths

    def test_detects_modified_file(self, mock_session):
        call_count = [0]
        def side_effect(*args, **kwargs):
            mock = MagicMock()
            if call_count[0] == 0:
                mock.collect.return_value = [
                    {"name": "@repo/commits/abc/a.py", "size": 150},
                ]
            else:
                mock.collect.return_value = [
                    {"name": "@repo/commits/def/a.py", "size": 100},
                ]
            call_count[0] += 1
            return mock

        mock_session.sql.side_effect = side_effect

        changed = file_reader.get_changed_files(
            mock_session, "@repo", "abc", "def", {".py"}
        )
        assert len(changed) == 1
