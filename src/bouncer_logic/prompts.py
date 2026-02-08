"""Prompt templates and JSON response schemas for Cortex AI calls."""

import json
import re

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


# -- File role inference -----------------------------------------------------

_ROLE_PATTERNS = [
    (re.compile(r"(^|/)api/", re.IGNORECASE), "API endpoint handler"),
    (re.compile(r"(^|/)routes?/", re.IGNORECASE), "Route handler"),
    (re.compile(r"(^|/)controllers?/", re.IGNORECASE), "Controller"),
    (re.compile(r"(^|/)auth", re.IGNORECASE), "Authentication module"),
    (re.compile(r"(^|/)login", re.IGNORECASE), "Login handler"),
    (re.compile(r"(^|/)middleware", re.IGNORECASE), "Middleware"),
    (re.compile(r"(^|/)db/", re.IGNORECASE), "Database access layer"),
    (re.compile(r"(^|/)models?/", re.IGNORECASE), "Data model"),
    (re.compile(r"(^|/)config", re.IGNORECASE), "Configuration file"),
    (re.compile(r"(^|/)handlers?/", re.IGNORECASE), "Request handler"),
    (re.compile(r"(^|/)utils?/", re.IGNORECASE), "Utility module"),
    (re.compile(r"(^|/)services?/", re.IGNORECASE), "Service layer"),
    (re.compile(r"\.github/workflows/", re.IGNORECASE), "CI/CD workflow"),
]


def _infer_file_role(file_path: str) -> str:
    """Map path patterns to a human-readable role description."""
    for pattern, role in _ROLE_PATTERNS:
        if pattern.search(file_path):
            return role
    return "Source file"


# -- Prompt builders ---------------------------------------------------------

def build_triage_prompt(
    file_content: str,
    file_path: str,
    repo_context: str = "",
    git_context: str = "",
) -> str:
    """Build the fast triage prompt with enriched context."""
    role = _infer_file_role(file_path)

    context_section = ""
    if repo_context:
        context_section += f"Project: {repo_context}\n"
    context_section += f"File: {file_path}\nRole: {role}\n"
    if git_context:
        context_section += f"Git history: {git_context}\n"

    return (
        "You are a security auditor. Analyze the following code for "
        "real, exploitable vulnerabilities.\n\n"
        f"{context_section}\n"
        "The code below contains security-relevant sections extracted from this file. "
        "Each section is labeled with why it was flagged for review.\n\n"
        "Focus on:\n"
        "- SQL Injection, Command Injection, XSS, SSRF\n"
        "- Broken Authentication / Authorization\n"
        "- Sensitive Data Exposure (hardcoded secrets, API keys)\n"
        "- Insecure Deserialization\n"
        "- Security Misconfiguration\n"
        "- Path Traversal\n\n"
        "Only report REAL vulnerabilities with HIGH confidence. "
        "Do NOT flag theoretical issues, well-sanitized code, or standard library usage.\n"
        "For each finding provide severity, vulnerability type, description, "
        "confidence (0-1), line number, and the vulnerable code snippet.\n"
        "If no real vulnerabilities are found, return an empty findings array.\n\n"
        "SOURCE CODE:\n```\n"
        f"{file_content}\n"
        "```\n\n"
        "Return your analysis as structured JSON."
    )


def build_deep_analysis_prompt(
    file_content: str,
    file_path: str,
    triage_findings: list,
    repo_context: str = "",
    git_context: str = "",
) -> str:
    """Build the deep analysis prompt for pro model."""
    role = _infer_file_role(file_path)
    findings_str = json.dumps(triage_findings, indent=2)

    context_section = ""
    if repo_context:
        context_section += f"Project: {repo_context}\n"
    context_section += f"File: {file_path}\nRole: {role}\n"
    if git_context:
        context_section += f"Git history: {git_context}\n"

    return (
        "You are an expert application security researcher. A preliminary "
        "scan flagged the following potential vulnerabilities. Your job is to:\n\n"
        "1. CONFIRM or REJECT each finding with detailed reasoning.\n"
        "2. Provide a specific, working code fix for each confirmed vulnerability.\n"
        "3. Identify any ADDITIONAL vulnerabilities the preliminary scan missed.\n"
        "4. Assign CWE IDs where applicable.\n\n"
        f"{context_section}\n"
        f"PRELIMINARY FINDINGS:\n{findings_str}\n\n"
        "SOURCE CODE:\n```\n"
        f"{file_content}\n"
        "```\n\n"
        "For each confirmed finding provide: severity, vuln_type, description, "
        "fix_suggestion (corrected code), confidence, attack_vector, and CWE ID.\n"
        "Return your analysis as structured JSON."
    )
