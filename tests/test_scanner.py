"""Tests for bouncer_logic.scanner."""

import json
from unittest.mock import MagicMock, patch

import pytest

from bouncer_logic import scanner, config


@pytest.fixture
def repo_row():
    """A mock Row that behaves like a Snowpark Row with as_dict()."""
    row = MagicMock()
    row.as_dict.return_value = {
        "REPO_ID": 1,
        "REPO_NAME": "test-org/test-repo",
        "REPO_URL": "https://github.com/test-org/test-repo",
        "GIT_REPO_NAME": "GITHUB_REPO",
        "DEFAULT_BRANCH": "main",
        "FILE_EXTENSIONS": [".py", ".js"],
        "IS_ACTIVE": True,
        "DEEP_SCAN": False,
    }
    return row


class TestRunSecurityScan:
    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.file_reader")
    def test_scans_all_files(self, mock_fr, mock_cc, mock_rf, mock_session, repo_row):
        # Setup: one repo, two files
        mock_session.sql.return_value.collect.side_effect = [
            [repo_row],  # _get_repo_configs
            [],           # _create_scan_record
        ]
        mock_fr.list_files_in_repo.return_value = [
            {"path": "a.py", "full_stage_path": "@repo/branches/main/a.py"},
            {"path": "b.js", "full_stage_path": "@repo/branches/main/b.js"},
        ]
        mock_fr.read_file_content.return_value = "x = 1"
        mock_cc.triage_with_flash.return_value = {"findings": [], "file_risk_score": 0, "summary": "Clean"}
        mock_rf.persist_findings.return_value = 0

        result = scanner.run_security_scan(mock_session)

        assert mock_cc.triage_with_flash.call_count == 2
        assert result["total_files"] == 2

    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.file_reader")
    def test_triggers_deep_scan_for_high_severity(
        self, mock_fr, mock_cc, mock_rf, mock_session, repo_row
    ):
        mock_session.sql.return_value.collect.side_effect = [
            [repo_row],
            [],
        ]
        mock_fr.list_files_in_repo.return_value = [
            {"path": "a.py", "full_stage_path": "@repo/branches/main/a.py"},
        ]
        mock_fr.read_file_content.return_value = "dangerous()"
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
                    "severity": "HIGH",
                    "vuln_type": "SQLi",
                    "description": "confirmed",
                    "fix_suggestion": "fix",
                    "confidence": 0.95,
                }
            ],
            "summary": "Confirmed",
        }
        mock_rf.format_finding.return_value = {"FINDING_ID": "test"}
        mock_rf.persist_findings.return_value = 1

        result = scanner.run_security_scan(mock_session)

        mock_cc.deep_analyze_with_pro.assert_called_once()
        assert result["total_findings"] == 1

    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.file_reader")
    def test_skips_deep_scan_for_low_severity(
        self, mock_fr, mock_cc, mock_rf, mock_session, repo_row
    ):
        mock_session.sql.return_value.collect.side_effect = [
            [repo_row],
            [],
        ]
        mock_fr.list_files_in_repo.return_value = [
            {"path": "a.py", "full_stage_path": "@repo/branches/main/a.py"},
        ]
        mock_fr.read_file_content.return_value = "x = 1"
        mock_cc.triage_with_flash.return_value = {
            "findings": [
                {"severity": "LOW", "vuln_type": "Info", "description": "minor", "confidence": 0.9}
            ],
            "file_risk_score": 0.2,
            "summary": "Minor",
        }
        mock_rf.format_finding.return_value = {"FINDING_ID": "test"}
        mock_rf.persist_findings.return_value = 1

        scanner.run_security_scan(mock_session)

        mock_cc.deep_analyze_with_pro.assert_not_called()

    @patch("bouncer_logic.scanner.result_formatter")
    @patch("bouncer_logic.scanner.cortex_client")
    @patch("bouncer_logic.scanner.file_reader")
    def test_handles_scan_error(
        self, mock_fr, mock_cc, mock_rf, mock_session, repo_row
    ):
        mock_session.sql.return_value.collect.side_effect = [
            [repo_row],
            [],
        ]
        mock_fr.list_files_in_repo.side_effect = RuntimeError("connection lost")

        result = scanner.run_security_scan(mock_session)

        assert len(result["errors"]) == 1
        assert "connection lost" in result["errors"][0]["error"]
        mock_rf.update_scan_status.assert_called()
