"""Tests for bouncer_logic.cortex_client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from bouncer_logic import cortex_client, config
from bouncer_logic.cortex_client import CortexCallError, CortexTimeoutError


class TestCallCortexComplete:
    def test_uses_parameterized_query(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        cortex_client.call_cortex_complete(
            mock_conn, config.MODEL_FLASH, "test prompt"
        )

        sql_string = cursor.execute.call_args[0][0]
        assert "%s" in sql_string, "SQL must use parameterized placeholders"
        assert "{" not in sql_string, "SQL must not contain f-string interpolation"

    def test_passes_correct_model(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        cortex_client.call_cortex_complete(
            mock_conn, config.MODEL_FLASH, "prompt"
        )

        params = cursor.execute.call_args[0][1]
        assert config.MODEL_FLASH in params

    def test_parses_json_response(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        result = cortex_client.call_cortex_complete(
            mock_conn, config.MODEL_FLASH, "prompt"
        )

        assert "findings" in result
        assert len(result["findings"]) == 1

    def test_with_response_format(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        schema = {"type": "object", "properties": {}}
        cortex_client.call_cortex_complete(
            mock_conn, config.MODEL_FLASH, "prompt", response_format=schema
        )

        sql_string = cursor.execute.call_args[0][0]
        assert "PARSE_JSON" in sql_string
        assert "%s" in sql_string
        # Verify the options JSON includes response_format
        params = cursor.execute.call_args[0][1]
        assert "response_format" in params[2]


class TestRetryLogic:
    def test_retries_on_failure(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.execute.side_effect = [
            RuntimeError("transient error"),
            None,
        ]
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        with patch("bouncer_logic.cortex_client.time.sleep"):
            result = cortex_client.call_cortex_complete(
                mock_conn, config.MODEL_FLASH, "prompt", max_retries=2
            )

        assert "findings" in result
        assert cursor.execute.call_count == 2

    def test_raises_after_max_retries(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.execute.side_effect = RuntimeError("persistent")

        with patch("bouncer_logic.cortex_client.time.sleep"):
            with pytest.raises(CortexCallError, match="persistent"):
                cortex_client.call_cortex_complete(
                    mock_conn, config.MODEL_FLASH, "prompt", max_retries=2
                )

        assert cursor.execute.call_count == 2

    def test_timeout_raises_immediately(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]

        def slow_execute(*args, **kwargs):
            import time
            time.sleep(0.05)

        cursor.execute.side_effect = slow_execute
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        with pytest.raises(CortexTimeoutError):
            cortex_client.call_cortex_complete(
                mock_conn, config.MODEL_FLASH, "prompt", timeout=0
            )


class TestTriageWithFlash:
    def test_calls_flash_model(self, mock_conn, sample_triage_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.fetchall.return_value = [(json.dumps(sample_triage_response),)]

        cortex_client.triage_with_flash(mock_conn, "code", "file.py")

        params = cursor.execute.call_args[0][1]
        assert config.MODEL_FLASH in params


class TestDeepAnalyzeWithPro:
    def test_calls_pro_model(self, mock_conn, sample_deep_response):
        cursor = mock_conn.cursor.return_value
        cursor.description = [("RESPONSE",)]
        cursor.fetchall.return_value = [(json.dumps(sample_deep_response),)]

        cortex_client.deep_analyze_with_pro(
            mock_conn, "code", "file.py", [{"severity": "HIGH"}]
        )

        params = cursor.execute.call_args[0][1]
        assert config.MODEL_PRO in params

    def test_returns_none_on_failure(self, mock_conn):
        cursor = mock_conn.cursor.return_value
        cursor.execute.side_effect = RuntimeError("down")

        with patch("bouncer_logic.cortex_client.time.sleep"):
            result = cortex_client.deep_analyze_with_pro(
                mock_conn, "code", "file.py", [{"severity": "HIGH"}]
            )

        assert result is None
