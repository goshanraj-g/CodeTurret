"""Snowflake Cortex AI client for vulnerability analysis."""

import json
import logging
import time
from typing import Optional

from bouncer_logic import config, prompts

logger = logging.getLogger(__name__)


class CortexTimeoutError(Exception):
    """Raised when a Cortex call exceeds the configured timeout."""


class CortexCallError(Exception):
    """Raised when a Cortex call fails after all retries."""


def call_cortex_complete(
    conn,
    model: str,
    prompt: str,
    response_format: Optional[dict] = None,
    timeout: int = config.CORTEX_TIMEOUT_SECONDS,
    max_retries: int = config.CORTEX_MAX_RETRIES,
) -> dict:
    """Call SNOWFLAKE.CORTEX.COMPLETE with parameterized SQL.

    Includes timeout enforcement and retry logic.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            start = time.time()
            result = _execute_cortex_sql(conn, model, prompt, response_format)
            elapsed = time.time() - start

            if elapsed > timeout:
                raise CortexTimeoutError(
                    f"Cortex call took {elapsed:.1f}s (limit {timeout}s)"
                )

            raw = result[0]["RESPONSE"]
            parsed = json.loads(raw) if isinstance(raw, str) else raw

            # Structured output returns {"structured_output": [{"raw_message": ...}]}
            if isinstance(parsed, dict) and "structured_output" in parsed:
                rm = parsed["structured_output"][0]["raw_message"]
                return json.loads(rm) if isinstance(rm, str) else rm
            # Message-array format returns {"choices": [{"messages": "..."}]}
            if isinstance(parsed, dict) and "choices" in parsed:
                msg = parsed["choices"][0]["messages"]
                return json.loads(msg) if isinstance(msg, str) else msg
            return parsed

        except CortexTimeoutError:
            raise
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Cortex call attempt %d/%d failed: %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                time.sleep(config.CORTEX_RETRY_DELAY_SECONDS)

    raise CortexCallError(
        f"Cortex call failed after {max_retries} attempts: {last_error}"
    )


def _execute_cortex_sql(conn, model: str, prompt: str, response_format: Optional[dict]) -> list:
    """Execute the raw Cortex SQL via snowflake-connector cursor."""
    cur = conn.cursor()
    try:
        if response_format:
            # Structured output requires message-array format for the prompt
            # and returns structured_output instead of plain text.
            messages = [{"role": "user", "content": prompt}]
            options = {
                "response_format": {
                    "type": "json",
                    "schema": response_format,
                }
            }
            cur.execute(
                """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    %s,
                    PARSE_JSON(%s),
                    PARSE_JSON(%s)
                ) AS RESPONSE
                """,
                (model, json.dumps(messages), json.dumps(options)),
            )
        else:
            cur.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE",
                (model, prompt),
            )
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cur.close()


def triage_with_flash(
    conn,
    file_content: str,
    file_path: str,
    repo_context: str = "",
    git_context: str = "",
) -> dict:
    """First pass: fast triage."""
    prompt = prompts.build_triage_prompt(
        file_content, file_path,
        repo_context=repo_context,
        git_context=git_context,
    )
    return call_cortex_complete(
        conn,
        config.MODEL_FLASH,
        prompt,
        response_format=prompts.TRIAGE_RESPONSE_SCHEMA,
    )


def deep_analyze_with_pro(
    conn,
    file_content: str,
    file_path: str,
    triage_findings: list,
    repo_context: str = "",
    git_context: str = "",
) -> dict:
    """Second pass: deep analysis with pro model.

    Returns None on failure so the caller can fall back to flash results.
    """
    prompt = prompts.build_deep_analysis_prompt(
        file_content, file_path, triage_findings,
        repo_context=repo_context,
        git_context=git_context,
    )
    try:
        return call_cortex_complete(
            conn,
            config.MODEL_PRO,
            prompt,
            response_format=prompts.DEEP_ANALYSIS_RESPONSE_SCHEMA,
        )
    except (CortexCallError, CortexTimeoutError) as exc:
        logger.warning(
            "Pro analysis failed for %s, falling back to flash: %s",
            file_path, exc,
        )
        return None
