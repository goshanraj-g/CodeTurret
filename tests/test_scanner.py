"""Tests for bouncer_logic.scanner."""

import json
from unittest.mock import MagicMock, patch

import pytest

from bouncer_logic import scanner, config


def _passthrough_prioritize(files, contents=None, **kwargs):
    """Return files as-is with a risk_score added (no filtering)."""
    return [{**f, "risk_score": 2} for f in files]


@pytest.fixture
def mock_conn():
    """A mocked snowflake.connector connection for scanner tests."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)  # repo_id
    conn.cursor.return_value = cursor
    return conn


def _scanner_patches():
    """Return a list of patch decorators for scanner tests."""
    return [
        patch("bouncer_logic.scanner.github_client"),
        patch("bouncer_logic.scanner.cortex_client"),
        patch("bouncer_logic.scanner.result_formatter"),
        patch("bouncer_logic.scanner.risk_assessor"),
        patch("bouncer_logic.scanner.git_intel"),
        patch("bouncer_logic.scanner.code_extractor"),
        patch("bouncer_logic.scanner.config.get_snowflake_connection"),
    ]


class TestRunSecurityScan:
    @patch("bouncer_logic.scanner.config.get_snowflake_connection")
    @patch("bouncer_logic.scanner.code_extractor")
    @patch("bouncer_logic.scanner.git_intel")
    @patch("bouncer_logic.scanner.risk_assessor")
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.github_client")
    def test_scans_all_files(
        self, mock_gh, mock_cc, mock_rf, mock_ra, mock_gi, mock_ce, mock_get_conn, mock_conn
    ):
        mock_get_conn.return_value = mock_conn
        mock_gh.clone_repo.return_value = "/tmp/repo"
        mock_gh.list_repo_files.return_value = [
            {"path": "a.py", "full_path": "/tmp/repo/a.py"},
            {"path": "b.js", "full_path": "/tmp/repo/b.js"},
        ]
        mock_gh.read_file_content.return_value = "x = 1"
        mock_gi.get_hot_files.return_value = {}
        mock_gi.get_security_commits.return_value = {}
        mock_gi.get_repo_context.return_value = ""
        mock_ce.extract_security_snippets.return_value = []
        mock_ce.build_focused_content.return_value = ""
        mock_ra.prioritize_files.side_effect = _passthrough_prioritize
        mock_cc.triage_with_flash.return_value = {
            "findings": [], "file_risk_score": 0, "summary": "Clean"
        }
        mock_rf.persist_findings.return_value = 0

        result = scanner.run_security_scan("https://github.com/test/repo")

        assert mock_cc.triage_with_flash.call_count == 2
        assert result["total_files"] == 2
        mock_gh.cleanup_repo.assert_called_once()

    @patch("bouncer_logic.scanner.config.get_snowflake_connection")
    @patch("bouncer_logic.scanner.code_extractor")
    @patch("bouncer_logic.scanner.git_intel")
    @patch("bouncer_logic.scanner.risk_assessor")
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.github_client")
    def test_triggers_deep_scan_for_high_severity(
        self, mock_gh, mock_cc, mock_rf, mock_ra, mock_gi, mock_ce, mock_get_conn, mock_conn
    ):
        mock_get_conn.return_value = mock_conn
        mock_gh.clone_repo.return_value = "/tmp/repo"
        mock_gh.list_repo_files.return_value = [
            {"path": "a.py", "full_path": "/tmp/repo/a.py"},
        ]
        mock_gh.read_file_content.return_value = "dangerous()"
        mock_gi.get_hot_files.return_value = {}
        mock_gi.get_security_commits.return_value = {}
        mock_gi.get_repo_context.return_value = ""
        mock_ce.extract_security_snippets.return_value = []
        mock_ce.build_focused_content.return_value = ""
        mock_ra.prioritize_files.side_effect = _passthrough_prioritize
        mock_cc.triage_with_flash.return_value = {
            "findings": [
                {"severity": "HIGH", "vuln_type": "SQLi", "description": "bad", "confidence": 0.9}
            ],
            "file_risk_score": 0.8,
            "summary": "Issue found",
        }
        mock_cc.deep_analyze_with_pro.return_value = {
            "findings": [
                {
                    "severity": "HIGH", "vuln_type": "SQLi",
                    "description": "confirmed", "fix_suggestion": "fix",
                    "confidence": 0.95,
                }
            ],
            "summary": "Confirmed",
        }
        mock_rf.format_finding.return_value = {"FINDING_ID": "test"}
        mock_rf.persist_findings.return_value = 1

        result = scanner.run_security_scan("https://github.com/test/repo")

        mock_cc.deep_analyze_with_pro.assert_called_once()
        assert result["total_findings"] == 1

    @patch("bouncer_logic.scanner.config.get_snowflake_connection")
    @patch("bouncer_logic.scanner.code_extractor")
    @patch("bouncer_logic.scanner.git_intel")
    @patch("bouncer_logic.scanner.risk_assessor")
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.github_client")
    def test_skips_deep_scan_for_low_severity(
        self, mock_gh, mock_cc, mock_rf, mock_ra, mock_gi, mock_ce, mock_get_conn, mock_conn
    ):
        mock_get_conn.return_value = mock_conn
        mock_gh.clone_repo.return_value = "/tmp/repo"
        mock_gh.list_repo_files.return_value = [
            {"path": "a.py", "full_path": "/tmp/repo/a.py"},
        ]
        mock_gh.read_file_content.return_value = "x = 1"
        mock_gi.get_hot_files.return_value = {}
        mock_gi.get_security_commits.return_value = {}
        mock_gi.get_repo_context.return_value = ""
        mock_ce.extract_security_snippets.return_value = []
        mock_ce.build_focused_content.return_value = ""
        mock_ra.prioritize_files.side_effect = _passthrough_prioritize
        mock_cc.triage_with_flash.return_value = {
            "findings": [
                {"severity": "LOW", "vuln_type": "Info", "description": "minor", "confidence": 0.9}
            ],
            "file_risk_score": 0.2,
            "summary": "Minor",
        }
        mock_rf.format_finding.return_value = {"FINDING_ID": "test"}
        mock_rf.persist_findings.return_value = 1

        scanner.run_security_scan("https://github.com/test/repo")

        mock_cc.deep_analyze_with_pro.assert_not_called()

    @patch("bouncer_logic.scanner.config.get_snowflake_connection")
    @patch("bouncer_logic.scanner.code_extractor")
    @patch("bouncer_logic.scanner.git_intel")
    @patch("bouncer_logic.scanner.risk_assessor")
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.github_client")
    def test_handles_clone_error(
        self, mock_gh, mock_cc, mock_rf, mock_ra, mock_gi, mock_ce, mock_get_conn, mock_conn
    ):
        mock_get_conn.return_value = mock_conn
        mock_gh.clone_repo.side_effect = RuntimeError("connection lost")

        result = scanner.run_security_scan("https://github.com/test/repo")

        assert len(result["errors"]) == 1
        assert "connection lost" in result["errors"][0]["error"]
        mock_rf.update_scan_status.assert_called()

    @patch("bouncer_logic.scanner.config.get_snowflake_connection")
    @patch("bouncer_logic.scanner.code_extractor")
    @patch("bouncer_logic.scanner.git_intel")
    @patch("bouncer_logic.scanner.risk_assessor")
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.github_client")
    def test_falls_back_to_flash_when_pro_fails(
        self, mock_gh, mock_cc, mock_rf, mock_ra, mock_gi, mock_ce, mock_get_conn, mock_conn
    ):
        mock_get_conn.return_value = mock_conn
        mock_gh.clone_repo.return_value = "/tmp/repo"
        mock_gh.list_repo_files.return_value = [
            {"path": "a.py", "full_path": "/tmp/repo/a.py"},
        ]
        mock_gh.read_file_content.return_value = "dangerous()"
        mock_gi.get_hot_files.return_value = {}
        mock_gi.get_security_commits.return_value = {}
        mock_gi.get_repo_context.return_value = ""
        mock_ce.extract_security_snippets.return_value = []
        mock_ce.build_focused_content.return_value = ""
        mock_ra.prioritize_files.side_effect = _passthrough_prioritize
        mock_cc.triage_with_flash.return_value = {
            "findings": [
                {"severity": "CRITICAL", "vuln_type": "RCE", "description": "bad", "confidence": 0.8}
            ],
            "file_risk_score": 0.9,
            "summary": "Critical",
        }
        mock_cc.deep_analyze_with_pro.return_value = None
        mock_rf.format_finding.return_value = {"FINDING_ID": "test"}
        mock_rf.persist_findings.return_value = 1

        result = scanner.run_security_scan("https://github.com/test/repo")

        assert result["total_findings"] == 1
        call_args = mock_rf.format_finding.call_args
        assert call_args[0][4] == config.MODEL_FLASH

    @patch("bouncer_logic.scanner.config.get_snowflake_connection")
    @patch("bouncer_logic.scanner.code_extractor")
    @patch("bouncer_logic.scanner.git_intel")
    @patch("bouncer_logic.scanner.risk_assessor")
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.github_client")
    def test_skipped_files_counted(
        self, mock_gh, mock_cc, mock_rf, mock_ra, mock_gi, mock_ce, mock_get_conn, mock_conn
    ):
        mock_get_conn.return_value = mock_conn
        mock_gh.clone_repo.return_value = "/tmp/repo"
        mock_gh.list_repo_files.return_value = [
            {"path": "a.py", "full_path": "/tmp/repo/a.py"},
            {"path": "README.md", "full_path": "/tmp/repo/README.md"},
            {"path": "b.py", "full_path": "/tmp/repo/b.py"},
        ]
        mock_gh.read_file_content.return_value = "x = 1"
        mock_gi.get_hot_files.return_value = {}
        mock_gi.get_security_commits.return_value = {}
        mock_gi.get_repo_context.return_value = ""
        mock_ce.extract_security_snippets.return_value = []
        mock_ce.build_focused_content.return_value = ""
        mock_ra.prioritize_files.return_value = [
            {"path": "a.py", "full_path": "/tmp/repo/a.py", "risk_score": 1},
            {"path": "b.py", "full_path": "/tmp/repo/b.py", "risk_score": 1},
        ]
        mock_cc.triage_with_flash.return_value = {
            "findings": [], "file_risk_score": 0, "summary": "Clean"
        }
        mock_rf.persist_findings.return_value = 0

        result = scanner.run_security_scan("https://github.com/test/repo")

        assert result["skipped_files"] == 1
        assert result["total_files"] == 2
