"""Snowflake Cortex AI client for vulnerability analysis."""

import json
from typing import Optional

from snowflake.snowpark import Session

from bouncer_logic import config, prompts


def call_cortex_complete(
    session: Session,
    model: str,
    prompt: str,
    response_format: Optional[dict] = None,
) -> dict:
    """Call SNOWFLAKE.CORTEX.COMPLETE with parameterized SQL."""
    if response_format:
        result = session.sql(
            """
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                ?,
                ?,
                OBJECT_CONSTRUCT(
                    'response_format', OBJECT_CONSTRUCT(
                        'type', 'json',
                        'schema', PARSE_JSON(?)
                    )
                )
            ) AS response
            """,
            params=[model, prompt, json.dumps(response_format)],
        ).collect()
    else:
        result = session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS response",
            params=[model, prompt],
        ).collect()

    raw = result[0]["RESPONSE"]
    return json.loads(raw) if isinstance(raw, str) else raw


def triage_with_flash(
    session: Session,
    file_content: str,
    file_path: str,
) -> dict:
    """First pass: fast triage with gemini-3.0-flash."""
    prompt = prompts.build_triage_prompt(file_content, file_path)
    return call_cortex_complete(
        session,
        config.MODEL_FLASH,
        prompt,
        response_format=prompts.TRIAGE_RESPONSE_SCHEMA,
    )


def deep_analyze_with_pro(
    session: Session,
    file_content: str,
    file_path: str,
    triage_findings: list,
) -> dict:
    """Second pass: deep analysis with gemini-3.0-pro."""
    prompt = prompts.build_deep_analysis_prompt(
        file_content, file_path, triage_findings
    )
    return call_cortex_complete(
        session,
        config.MODEL_PRO,
        prompt,
        response_format=prompts.DEEP_ANALYSIS_RESPONSE_SCHEMA,
    )
