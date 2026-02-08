"""Tests for bouncer_logic.result_formatter."""

import json
from unittest.mock import MagicMock, call

from bouncer_logic import result_formatter


class TestFormatFinding:
    def test_all_required_fields_present(self):
        raw = {
            "severity": "HIGH",
            "vuln_type": "XSS",
            "description": "Reflected XSS via query param.",
            "confidence": 0.9,
            "line_number": 10,
            "code_snippet": "<script>alert(1)</script>",
        }
        result = result_formatter.format_finding(
            "scan-1", 1, "app.js", raw, "gemini-3.0-flash", {"raw": True}
        )

        required_keys = {
            "FINDING_ID", "SCAN_ID", "REPO_ID", "FILE_PATH",
            "SEVERITY", "VULN_TYPE", "DESCRIPTION", "MODEL_USED",
            "CONFIDENCE", "RAW_RESPONSE",
        }
        assert required_keys.issubset(result.keys())

    def test_generates_uuid(self):
        raw = {"severity": "LOW", "vuln_type": "Info", "description": "d"}
        r1 = result_formatter.format_finding("s", 1, "f", raw, "m", {})
        r2 = result_formatter.format_finding("s", 1, "f", raw, "m", {})
        assert r1["FINDING_ID"] != r2["FINDING_ID"]

    def test_defaults_for_optional_fields(self):
        raw = {"severity": "MEDIUM", "vuln_type": "Misc", "description": "x"}
        result = result_formatter.format_finding("s", 1, "f.py", raw, "m", {})
        assert result["FIX_SUGGESTION"] == ""
        assert result["CONFIDENCE"] == 0.0

    def test_raw_response_is_json_string(self):
        raw = {"severity": "LOW", "vuln_type": "t", "description": "d"}
        response = {"findings": [raw]}
        result = result_formatter.format_finding("s", 1, "f", raw, "m", response)
        parsed = json.loads(result["RAW_RESPONSE"])
        assert "findings" in parsed


class TestPersistFindings:
    def test_empty_list_returns_zero(self, mock_session):
        assert result_formatter.persist_findings(mock_session, []) == 0
        mock_session.create_dataframe.assert_not_called()

    def test_returns_count(self, mock_session):
        findings = [{"FINDING_ID": "a"}, {"FINDING_ID": "b"}]
        count = result_formatter.persist_findings(mock_session, findings)
        assert count == 2
        mock_session.create_dataframe.assert_called_once_with(findings)


class TestUpdateScanStatus:
    def test_uses_parameterized_sql(self, mock_session):
        result_formatter.update_scan_status(
            mock_session, "scan-1", "COMPLETED", 5, 3
        )

        sql_string = mock_session.sql.call_args[0][0]
        assert "?" in sql_string
        assert "{" not in sql_string

    def test_includes_error_message(self, mock_session):
        result_formatter.update_scan_status(
            mock_session, "scan-1", "FAILED", error_message="boom"
        )

        params = mock_session.sql.call_args.kwargs.get("params", [])
        assert "boom" in params
