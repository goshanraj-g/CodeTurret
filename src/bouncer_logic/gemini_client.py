"""Google Gemini AI client for vulnerability analysis.

Uses the new google-genai SDK (replacement for deprecated google-generativeai).
"""

import json
import logging
import os
import time
from typing import Optional

from google import genai
from google.genai import types

from bouncer_logic import config, prompts

logger = logging.getLogger(__name__)


class GeminiCallError(Exception):
    """Raised when a Gemini call fails after all retries."""


class GeminiTimeoutError(Exception):
    """Raised when a Gemini call exceeds the configured timeout."""


def _get_client() -> genai.Client:
    """Configure and return the Gemini client."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiCallError("GEMINI_API_KEY environment variable not set")
    return genai.Client(api_key=api_key)


def call_gemini(
    model_name: str,
    prompt: str,
    response_schema: Optional[dict] = None,
    timeout: int = config.GEMINI_TIMEOUT_SECONDS,
    max_retries: int = config.GEMINI_MAX_RETRIES,
) -> dict:
    """Call Gemini with retry logic and structured JSON output.

    Returns parsed JSON dict from the model response.
    """
    client = _get_client()
    last_error: Optional[Exception] = None

    generation_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
    )
    if response_schema:
        generation_config.response_schema = response_schema

    for attempt in range(1, max_retries + 1):
        try:
            start = time.time()
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )
            elapsed = time.time() - start

            if elapsed > timeout:
                raise GeminiTimeoutError(
                    f"Gemini call took {elapsed:.1f}s (limit {timeout}s)"
                )

            raw_text = response.text
            return json.loads(raw_text)

        except GeminiTimeoutError:
            raise
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Gemini call attempt %d/%d failed: %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                time.sleep(config.GEMINI_RETRY_DELAY_SECONDS)

    raise GeminiCallError(
        f"Gemini call failed after {max_retries} attempts: {last_error}"
    )


def triage_with_flash(
    file_content: str,
    file_path: str,
    repo_context: str = "",
    git_context: str = "",
) -> dict:
    """First pass: fast triage with Gemini Flash."""
    prompt = prompts.build_triage_prompt(
        file_content, file_path,
        repo_context=repo_context,
        git_context=git_context,
    )
    return call_gemini(
        config.MODEL_FLASH,
        prompt,
        response_schema=prompts.TRIAGE_RESPONSE_SCHEMA,
    )


def deep_analyze_with_pro(
    file_content: str,
    file_path: str,
    triage_findings: list,
    repo_context: str = "",
    git_context: str = "",
) -> dict:
    """Second pass: deep analysis with Gemini Pro.

    Returns None on failure so the caller can fall back to flash results.
    """
    prompt = prompts.build_deep_analysis_prompt(
        file_content, file_path, triage_findings,
        repo_context=repo_context,
        git_context=git_context,
    )
    try:
        return call_gemini(
            config.MODEL_PRO,
            prompt,
            response_schema=prompts.DEEP_ANALYSIS_RESPONSE_SCHEMA,
        )
    except (GeminiCallError, GeminiTimeoutError) as exc:
        logger.warning(
            "Pro analysis failed for %s, falling back to flash: %s",
            file_path, exc,
        )
        return None
