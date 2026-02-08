"""Tests for bouncer_logic.repo_chat."""

import json
from unittest.mock import MagicMock

import pytest

from bouncer_logic import repo_chat, config
from bouncer_logic.repo_chat import RepoChatError


class TestGetRepoContext:
    def test_returns_context_dict(self, mock_conn):
        cursor = mock_conn.cursor.return_value

        # Query 1: latest scan
        # Query 2: severity counts
        # Query 3: findings
        cursor.fetchone.return_value = (
            "scan-abc", 10, 3, "2024-01-15 10:00:00", "COMPLETED"
        )
        cursor.fetchall.side_effect = [
            # severity distribution
            [("HIGH", 2), ("MEDIUM", 1)],
            # findings
            [
                ("HIGH", "SQLi", "Bad query", "app.py", "Use params", 0.9, 42),
                ("HIGH", "XSS", "Script inject", "view.js", "Escape output", 0.85, 18),
                ("MEDIUM", "Info", "Debug left on", "config.py", "", 0.7, 5),
            ],
        ]
        cursor.description = [
            ("SEVERITY",), ("VULN_TYPE",), ("DESCRIPTION",),
            ("FILE_PATH",), ("FIX_SUGGESTION",), ("CONFIDENCE",), ("LINE_NUMBER",),
        ]

        result = repo_chat._get_repo_context(mock_conn, "test-repo")

        assert result is not None
        assert result["scan"]["scan_id"] == "scan-abc"
        assert result["scan"]["files_scanned"] == 10
        assert result["scan"]["findings_count"] == 3
        assert result["severity_counts"] == {"HIGH": 2, "MEDIUM": 1}
        assert len(result["findings"]) == 3
        assert result["findings"][0]["VULN_TYPE"] == "SQLi"

    def test_returns_none_when_no_scans(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = None

        result = repo_chat._get_repo_context(mock_conn, "unknown-repo")

        assert result is None

    def test_uses_parameterized_queries(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = (
            "scan-1", 5, 1, "2024-01-01", "COMPLETED"
        )
        cursor.fetchall.side_effect = [
            [("LOW", 1)],
            [("LOW", "Info", "Minor", "x.py", "", 0.5, 1)],
        ]
        cursor.description = [
            ("SEVERITY",), ("VULN_TYPE",), ("DESCRIPTION",),
            ("FILE_PATH",), ("FIX_SUGGESTION",), ("CONFIDENCE",), ("LINE_NUMBER",),
        ]

        repo_chat._get_repo_context(mock_conn, "repo")

        for call_args in cursor.execute.call_args_list:
            sql = call_args[0][0]
            assert "%s" in sql, f"SQL must use parameterized placeholders: {sql}"


class TestBuildChatPrompt:
    def test_includes_question(self):
        context = {
            "scan": {
                "scan_id": "s1", "files_scanned": 5,
                "findings_count": 1, "started_at": "2024-01-01", "status": "COMPLETED",
            },
            "severity_counts": {"HIGH": 1},
            "findings": [
                {
                    "SEVERITY": "HIGH", "VULN_TYPE": "SQLi",
                    "DESCRIPTION": "Bad query", "FILE_PATH": "app.py",
                    "FIX_SUGGESTION": "Use params", "CONFIDENCE": 0.9,
                    "LINE_NUMBER": 42,
                }
            ],
        }

        prompt = repo_chat._build_chat_prompt(context, "myrepo", "what is the biggest risk?")

        assert "what is the biggest risk?" in prompt

    def test_includes_findings(self):
        context = {
            "scan": {
                "scan_id": "s1", "files_scanned": 5,
                "findings_count": 2, "started_at": "2024-01-01", "status": "COMPLETED",
            },
            "severity_counts": {"CRITICAL": 1, "HIGH": 1},
            "findings": [
                {
                    "SEVERITY": "CRITICAL", "VULN_TYPE": "RCE",
                    "DESCRIPTION": "Remote code exec", "FILE_PATH": "api.py",
                    "FIX_SUGGESTION": "Sanitize input", "CONFIDENCE": 0.95,
                    "LINE_NUMBER": 10,
                },
                {
                    "SEVERITY": "HIGH", "VULN_TYPE": "SQLi",
                    "DESCRIPTION": "SQL injection", "FILE_PATH": "db.py",
                    "FIX_SUGGESTION": "", "CONFIDENCE": 0.8,
                    "LINE_NUMBER": None,
                },
            ],
        }

        prompt = repo_chat._build_chat_prompt(context, "repo", "summarize")

        assert "[CRITICAL] RCE" in prompt
        assert "api.py:10" in prompt
        assert "[HIGH] SQLi" in prompt
        assert "db.py" in prompt
        assert "Sanitize input" in prompt

    def test_includes_severity_distribution(self):
        context = {
            "scan": {
                "scan_id": "s1", "files_scanned": 10,
                "findings_count": 4, "started_at": "2024-01-01", "status": "COMPLETED",
            },
            "severity_counts": {"CRITICAL": 1, "HIGH": 2, "LOW": 1},
            "findings": [],
        }

        prompt = repo_chat._build_chat_prompt(context, "repo", "q?")

        assert "CRITICAL: 1" in prompt
        assert "HIGH: 2" in prompt
        assert "LOW: 1" in prompt

    def test_includes_repo_name(self):
        context = {
            "scan": {
                "scan_id": "s1", "files_scanned": 1,
                "findings_count": 0, "started_at": "2024-01-01", "status": "COMPLETED",
            },
            "severity_counts": {},
            "findings": [],
        }

        prompt = repo_chat._build_chat_prompt(context, "my-cool-app", "q?")

        assert "my-cool-app" in prompt

    def test_handles_no_findings(self):
        context = {
            "scan": {
                "scan_id": "s1", "files_scanned": 5,
                "findings_count": 0, "started_at": "2024-01-01", "status": "COMPLETED",
            },
            "severity_counts": {},
            "findings": [],
        }

        prompt = repo_chat._build_chat_prompt(context, "repo", "any issues?")

        assert "No findings." in prompt


class TestCallCortex:
    def test_parses_cortex_response(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = (json.dumps({
            "choices": [{"messages": "There are 2 critical vulnerabilities."}]
        }),)

        result = repo_chat._call_cortex(mock_conn, "test prompt")

        assert "2 critical vulnerabilities" in result

    def test_uses_chat_model(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = (json.dumps({
            "choices": [{"messages": "Answer"}]
        }),)

        repo_chat._call_cortex(mock_conn, "prompt")

        params = cursor.execute.call_args[0][1]
        assert config.CORTEX_CHAT_MODEL in params

    def test_raises_on_empty_response(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = None

        with pytest.raises(RepoChatError, match="Empty response"):
            repo_chat._call_cortex(mock_conn, "prompt")

    def test_raises_on_cortex_failure(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.execute.side_effect = RuntimeError("Cortex down")

        with pytest.raises(RepoChatError, match="Failed to get answer"):
            repo_chat._call_cortex(mock_conn, "prompt")


class TestAskAboutRepo:
    def test_returns_answer(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        # _get_repo_context queries
        cursor.fetchone.side_effect = [
            # latest scan
            ("scan-1", 5, 1, "2024-01-01", "COMPLETED"),
            # _call_cortex response
            (json.dumps({
                "choices": [{"messages": "The repo has 1 SQL injection vulnerability."}]
            }),),
        ]
        cursor.fetchall.side_effect = [
            # severity dist
            [("HIGH", 1)],
            # findings
            [("HIGH", "SQLi", "Bad query", "app.py", "Fix it", 0.9, 42)],
        ]
        cursor.description = [
            ("SEVERITY",), ("VULN_TYPE",), ("DESCRIPTION",),
            ("FILE_PATH",), ("FIX_SUGGESTION",), ("CONFIDENCE",), ("LINE_NUMBER",),
        ]

        result = repo_chat.ask_about_repo(mock_conn, "test-repo", "what issues?")

        assert "SQL injection" in result

    def test_returns_message_when_no_data(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = None

        result = repo_chat.ask_about_repo(mock_conn, "unknown", "question?")

        assert "No scan data found" in result
        assert "unknown" in result

    def test_uses_parameterized_sql(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.side_effect = [
            ("scan-1", 5, 1, "2024-01-01", "COMPLETED"),
            (json.dumps({"choices": [{"messages": "Answer"}]}),),
        ]
        cursor.fetchall.side_effect = [
            [("LOW", 1)],
            [("LOW", "Info", "Minor", "x.py", "", 0.5, 1)],
        ]
        cursor.description = [
            ("SEVERITY",), ("VULN_TYPE",), ("DESCRIPTION",),
            ("FILE_PATH",), ("FIX_SUGGESTION",), ("CONFIDENCE",), ("LINE_NUMBER",),
        ]

        repo_chat.ask_about_repo(mock_conn, "repo", "q?")

        for call_args in cursor.execute.call_args_list:
            sql = call_args[0][0]
            assert "%s" in sql
            assert "{" not in sql, "SQL must not contain f-string interpolation"
