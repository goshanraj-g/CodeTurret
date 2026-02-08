"""Tests for bouncer_logic.gemini_client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from bouncer_logic import gemini_client, config
from bouncer_logic.gemini_client import GeminiCallError, GeminiTimeoutError


def _mock_client_with_response(mock_genai, response_text):
    """Helper: set up mock genai.Client to return a response with given text."""
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text=response_text)
    return mock_client


class TestCallGemini:
    @patch("bouncer_logic.gemini_client.genai")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_parses_json_response(self, mock_genai, sample_triage_response):
        _mock_client_with_response(mock_genai, json.dumps(sample_triage_response))

        result = gemini_client.call_gemini(config.MODEL_FLASH, "test prompt")

        assert "findings" in result
        assert len(result["findings"]) == 1

    @patch("bouncer_logic.gemini_client.genai")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_uses_correct_model(self, mock_genai, sample_triage_response):
        mock_client = _mock_client_with_response(mock_genai, json.dumps(sample_triage_response))

        gemini_client.call_gemini(config.MODEL_FLASH, "prompt")

        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs[1]["model"] == config.MODEL_FLASH

    @patch("bouncer_logic.gemini_client.genai")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_configures_client_with_api_key(self, mock_genai, sample_triage_response):
        _mock_client_with_response(mock_genai, json.dumps(sample_triage_response))

        gemini_client.call_gemini(config.MODEL_FLASH, "prompt")

        mock_genai.Client.assert_called_once_with(api_key="test-key")

    @patch.dict("os.environ", {}, clear=True)
    def test_raises_without_api_key(self):
        with pytest.raises(GeminiCallError, match="GEMINI_API_KEY"):
            gemini_client.call_gemini(config.MODEL_FLASH, "prompt")


class TestRetryLogic:
    @patch("bouncer_logic.gemini_client.time.sleep")
    @patch("bouncer_logic.gemini_client.genai")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_retries_on_failure(self, mock_genai, mock_sleep, sample_triage_response):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = [
            RuntimeError("transient"),
            MagicMock(text=json.dumps(sample_triage_response)),
        ]

        result = gemini_client.call_gemini(
            config.MODEL_FLASH, "prompt", max_retries=2
        )

        assert "findings" in result
        assert mock_client.models.generate_content.call_count == 2

    @patch("bouncer_logic.gemini_client.time.sleep")
    @patch("bouncer_logic.gemini_client.genai")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_raises_after_max_retries(self, mock_genai, mock_sleep):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("persistent")

        with pytest.raises(GeminiCallError, match="persistent"):
            gemini_client.call_gemini(
                config.MODEL_FLASH, "prompt", max_retries=2
            )

        assert mock_client.models.generate_content.call_count == 2

    @patch("bouncer_logic.gemini_client.genai")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_timeout_raises_immediately(self, mock_genai, sample_triage_response):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        import time as real_time

        def slow_generate(*args, **kwargs):
            real_time.sleep(0.05)
            return MagicMock(text=json.dumps(sample_triage_response))

        mock_client.models.generate_content.side_effect = slow_generate

        with pytest.raises(GeminiTimeoutError):
            gemini_client.call_gemini(
                config.MODEL_FLASH, "prompt", timeout=0
            )


class TestTriageWithFlash:
    @patch("bouncer_logic.gemini_client.call_gemini")
    def test_calls_flash_model(self, mock_call, sample_triage_response):
        mock_call.return_value = sample_triage_response

        gemini_client.triage_with_flash("code", "file.py")

        mock_call.assert_called_once()
        assert mock_call.call_args[0][0] == config.MODEL_FLASH

    @patch("bouncer_logic.gemini_client.call_gemini")
    def test_passes_context_to_prompt(self, mock_call, sample_triage_response):
        mock_call.return_value = sample_triage_response

        gemini_client.triage_with_flash(
            "code", "file.py",
            repo_context="A web app",
            git_context="Modified 5 times",
        )

        prompt = mock_call.call_args[0][1]
        assert "A web app" in prompt
        assert "Modified 5 times" in prompt


class TestDeepAnalyzeWithPro:
    @patch("bouncer_logic.gemini_client.call_gemini")
    def test_calls_pro_model(self, mock_call, sample_deep_response):
        mock_call.return_value = sample_deep_response

        gemini_client.deep_analyze_with_pro(
            "code", "file.py", [{"severity": "HIGH"}]
        )

        mock_call.assert_called_once()
        assert mock_call.call_args[0][0] == config.MODEL_PRO

    @patch("bouncer_logic.gemini_client.call_gemini")
    def test_returns_none_on_failure(self, mock_call):
        mock_call.side_effect = GeminiCallError("down")

        result = gemini_client.deep_analyze_with_pro(
            "code", "file.py", [{"severity": "HIGH"}]
        )

        assert result is None
