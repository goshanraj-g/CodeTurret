"""Tests for bouncer_logic.cortex_client (analytics-only functions)."""

import json
from unittest.mock import MagicMock, call

import pytest

from bouncer_logic import cortex_client, config
from bouncer_logic.cortex_client import CortexCallError


class TestSummarizeFindings:
    def test_returns_summary_string(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        # First call: SELECT findings
        cursor.fetchall.return_value = [
            ("app.py", "HIGH", "SQL Injection", "Bad query", 0.9),
        ]
        cursor.description = [
            ("FILE_PATH",), ("SEVERITY",), ("VULN_TYPE",),
            ("DESCRIPTION",), ("CONFIDENCE",),
        ]
        # Second call: CORTEX.COMPLETE
        cortex_response = json.dumps({
            "choices": [{"messages": "- 1 HIGH severity SQL Injection in app.py"}]
        })
        cursor.fetchone.return_value = (cortex_response,)

        result = cortex_client.summarize_findings(mock_conn, "scan-123")

        assert "SQL Injection" in result
        # Verify parameterized query used
        first_call_sql = cursor.execute.call_args_list[0][0][0]
        assert "%s" in first_call_sql

    def test_returns_message_when_no_findings(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchall.return_value = []

        result = cortex_client.summarize_findings(mock_conn, "scan-empty")

        assert result == "No findings to summarize."

    def test_raises_on_cortex_error(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchall.return_value = [
            ("app.py", "HIGH", "XSS", "Script injection", 0.8),
        ]
        cursor.description = [
            ("FILE_PATH",), ("SEVERITY",), ("VULN_TYPE",),
            ("DESCRIPTION",), ("CONFIDENCE",),
        ]
        cursor.fetchone.side_effect = RuntimeError("Cortex unavailable")

        with pytest.raises(CortexCallError, match="Failed to summarize"):
            cortex_client.summarize_findings(mock_conn, "scan-fail")

    def test_uses_analytics_model(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchall.return_value = [
            ("x.py", "MEDIUM", "Info", "test", 0.5),
        ]
        cursor.description = [
            ("FILE_PATH",), ("SEVERITY",), ("VULN_TYPE",),
            ("DESCRIPTION",), ("CONFIDENCE",),
        ]
        cursor.fetchone.return_value = (json.dumps({
            "choices": [{"messages": "Summary text"}]
        }),)

        cortex_client.summarize_findings(mock_conn, "scan-456")

        # The CORTEX.COMPLETE call should use the analytics model
        complete_call = cursor.execute.call_args_list[1]
        params = complete_call[0][1]
        assert config.CORTEX_ANALYTICS_MODEL in params


class TestClassifySeverityTrend:
    def test_returns_trend_data(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchall.return_value = [
            ("scan-1", "2024-01-01", "HIGH", 3),
            ("scan-2", "2024-01-02", "HIGH", 1),
        ]
        cursor.description = [
            ("SCAN_ID",), ("STARTED_AT",), ("SEVERITY",), ("CNT",),
        ]
        cursor.fetchone.return_value = (json.dumps({
            "choices": [{"messages": json.dumps({
                "trend": "improving",
                "summary": "Less findings",
                "severity_breakdown": {"HIGH": 4},
            })}]
        }),)

        result = cortex_client.classify_severity_trend(mock_conn, "test-repo")

        assert result["trend"] == "improving"

    def test_returns_no_data_when_empty(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchall.return_value = []

        result = cortex_client.classify_severity_trend(mock_conn, "empty-repo")

        assert result["trend"] == "no_data"

    def test_returns_error_on_failure(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.execute.side_effect = RuntimeError("Connection lost")

        result = cortex_client.classify_severity_trend(mock_conn, "bad-repo")

        assert result["trend"] == "error"
        assert "Connection lost" in result["error"]


class TestGetScanInsights:
    def test_returns_insights_dict(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        # First query: scan metadata
        cursor.fetchone.side_effect = [
            (10, 3, "test-repo"),  # meta
            (json.dumps({
                "choices": [{"messages": json.dumps({
                    "risk_level": "HIGH",
                    "summary": "3 vulnerabilities found",
                    "top_recommendations": ["Fix SQLi", "Update deps"],
                    "patterns": ["injection"],
                })}]
            }),),  # CORTEX.COMPLETE response
        ]
        # Second query: severity distribution
        cursor.fetchall.side_effect = [
            [("HIGH", 2), ("MEDIUM", 1)],  # severity dist
            [("HIGH", "SQLi", "Bad query", "app.py")],  # top findings
        ]
        cursor.description = [
            ("SEVERITY",), ("VULN_TYPE",), ("DESCRIPTION",), ("FILE_PATH",),
        ]

        result = cortex_client.get_scan_insights(mock_conn, "scan-789")

        assert result["risk_level"] == "HIGH"
        assert len(result["top_recommendations"]) == 2

    def test_returns_error_when_scan_not_found(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = None

        result = cortex_client.get_scan_insights(mock_conn, "nonexistent")

        assert result == {"error": "Scan not found"}

    def test_handles_cortex_failure_gracefully(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.fetchone.return_value = (5, 2, "repo")
        cursor.fetchall.side_effect = RuntimeError("Query failed")

        result = cortex_client.get_scan_insights(mock_conn, "scan-err")

        assert "error" in result
