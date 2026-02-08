"""Tests for bouncer_logic.cortex_client."""

import json
from unittest.mock import MagicMock

from bouncer_logic import cortex_client, config


class TestCallCortexComplete:
    def test_uses_parameterized_query(self, mock_session, sample_triage_response):
        mock_session.sql.return_value.collect.return_value = [
            {"RESPONSE": json.dumps(sample_triage_response)}
        ]

        cortex_client.call_cortex_complete(
            mock_session, config.MODEL_FLASH, "test prompt"
        )

        sql_string = mock_session.sql.call_args[0][0]
        assert "?" in sql_string, "SQL must use parameterized placeholders"
        assert "{" not in sql_string, "SQL must not contain f-string interpolation"

    def test_passes_correct_model(self, mock_session, sample_triage_response):
        mock_session.sql.return_value.collect.return_value = [
            {"RESPONSE": json.dumps(sample_triage_response)}
        ]

        cortex_client.call_cortex_complete(
            mock_session, config.MODEL_FLASH, "prompt"
        )

        params = mock_session.sql.call_args[1].get(
            "params", mock_session.sql.call_args[0][1] if len(mock_session.sql.call_args[0]) > 1 else None
        )
        # params passed as kwarg
        call_kwargs = mock_session.sql.call_args
        assert config.MODEL_FLASH in call_kwargs.kwargs.get("params", call_kwargs.args[1] if len(call_kwargs.args) > 1 else [])

    def test_parses_json_response(self, mock_session, sample_triage_response):
        mock_session.sql.return_value.collect.return_value = [
            {"RESPONSE": json.dumps(sample_triage_response)}
        ]

        result = cortex_client.call_cortex_complete(
            mock_session, config.MODEL_FLASH, "prompt"
        )

        assert "findings" in result
        assert len(result["findings"]) == 1

    def test_with_response_format(self, mock_session, sample_triage_response):
        mock_session.sql.return_value.collect.return_value = [
            {"RESPONSE": json.dumps(sample_triage_response)}
        ]

        schema = {"type": "object", "properties": {}}
        cortex_client.call_cortex_complete(
            mock_session, config.MODEL_FLASH, "prompt", response_format=schema
        )

        sql_string = mock_session.sql.call_args[0][0]
        assert "response_format" in sql_string
        assert "?" in sql_string


class TestTriageWithFlash:
    def test_calls_flash_model(self, mock_session, sample_triage_response):
        mock_session.sql.return_value.collect.return_value = [
            {"RESPONSE": json.dumps(sample_triage_response)}
        ]

        cortex_client.triage_with_flash(mock_session, "code", "file.py")

        params = mock_session.sql.call_args.kwargs.get("params", [])
        assert config.MODEL_FLASH in params


class TestDeepAnalyzeWithPro:
    def test_calls_pro_model(self, mock_session, sample_deep_response):
        mock_session.sql.return_value.collect.return_value = [
            {"RESPONSE": json.dumps(sample_deep_response)}
        ]

        cortex_client.deep_analyze_with_pro(
            mock_session, "code", "file.py", [{"severity": "HIGH"}]
        )

        params = mock_session.sql.call_args.kwargs.get("params", [])
        assert config.MODEL_PRO in params
