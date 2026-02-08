"""Prompt templates and JSON response schemas for Cortex AI calls."""

import json

# -- Response schemas for structured output ----------------------------------

TRIAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "integer"},
                    "severity": {
                        "type": "string",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    },
                    "vuln_type": {"type": "string"},
                    "description": {"type": "string"},
                    "confidence": {"type": "number"},
                    "code_snippet": {"type": "string"},
                },
                "required": [
                    "severity",
                    "vuln_type",
                    "description",
                    "confidence",
                ],
            },
        },
        "file_risk_score": {"type": "number"},
        "summary": {"type": "string"},
    },
    "required": ["findings", "file_risk_score", "summary"],
}

DEEP_ANALYSIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "integer"},
                    "severity": {
                        "type": "string",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    },
                    "vuln_type": {"type": "string"},
                    "description": {"type": "string"},
                    "fix_suggestion": {"type": "string"},
                    "confidence": {"type": "number"},
                    "code_snippet": {"type": "string"},
                    "attack_vector": {"type": "string"},
                    "cwe_id": {"type": "string"},
                },
                "required": [
                    "severity",
                    "vuln_type",
                    "description",
                    "fix_suggestion",
                    "confidence",
                ],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["findings", "summary"],
}


# -- Prompt builders ---------------------------------------------------------

def build_triage_prompt(file_content: str, file_path: str) -> str:
    """Build the fast triage prompt for gemini-3.0-flash."""
    return (
        "You are a security auditor. Analyze the following source code file "
        "for common vulnerabilities.\n\n"
        f"File: {file_path}\n\n"
        "Focus on:\n"
        "- SQL Injection, Command Injection, XSS, SSRF\n"
        "- Broken Authentication / Authorization\n"
        "- Sensitive Data Exposure (hardcoded secrets, API keys)\n"
        "- Insecure Deserialization\n"
        "- Security Misconfiguration\n"
        "- Path Traversal\n\n"
        "For each finding provide severity, vulnerability type, description, "
        "confidence (0-1), line number, and the vulnerable code snippet.\n"
        "If no vulnerabilities are found, return an empty findings array.\n\n"
        "SOURCE CODE:\n```\n"
        f"{file_content}\n"
        "```\n\n"
        "Return your analysis as structured JSON."
    )


def build_deep_analysis_prompt(
    file_content: str,
    file_path: str,
    triage_findings: list,
) -> str:
    """Build the deep analysis prompt for gemini-3.0-pro."""
    findings_str = json.dumps(triage_findings, indent=2)
    return (
        "You are an expert application security researcher. A preliminary "
        "scan flagged the following potential vulnerabilities. Your job is to:\n\n"
        "1. CONFIRM or REJECT each finding with detailed reasoning.\n"
        "2. Provide a specific, working code fix for each confirmed vulnerability.\n"
        "3. Identify any ADDITIONAL vulnerabilities the preliminary scan missed.\n"
        "4. Assign CWE IDs where applicable.\n\n"
        f"File: {file_path}\n\n"
        f"PRELIMINARY FINDINGS:\n{findings_str}\n\n"
        "SOURCE CODE:\n```\n"
        f"{file_content}\n"
        "```\n\n"
        "For each confirmed finding provide: severity, vuln_type, description, "
        "fix_suggestion (corrected code), confidence, attack_vector, and CWE ID.\n"
        "Return your analysis as structured JSON."
    )
