"""Tests for bouncer_logic.prompts."""

import json

from bouncer_logic import prompts


class TestTriagePrompt:
    def test_contains_file_path(self, sample_file_content):
        result = prompts.build_triage_prompt(sample_file_content, "src/app.py")
        assert "src/app.py" in result

    def test_contains_file_content(self, sample_file_content):
        result = prompts.build_triage_prompt(sample_file_content, "src/app.py")
        assert "sqlite3" in result

    def test_mentions_owasp_categories(self, sample_file_content):
        result = prompts.build_triage_prompt(sample_file_content, "f.py")
        assert "SQL Injection" in result
        assert "XSS" in result

    def test_empty_content(self):
        result = prompts.build_triage_prompt("", "empty.py")
        assert "empty.py" in result


class TestDeepAnalysisPrompt:
    def test_contains_preliminary_findings(self, sample_file_content):
        findings = [{"severity": "HIGH", "vuln_type": "SQLi"}]
        result = prompts.build_deep_analysis_prompt(
            sample_file_content, "f.py", findings
        )
        assert "SQLi" in result
        assert "CONFIRM or REJECT" in result

    def test_contains_file_path(self, sample_file_content):
        result = prompts.build_deep_analysis_prompt(
            sample_file_content, "src/x.ts", []
        )
        assert "src/x.ts" in result


class TestResponseSchemas:
    def test_triage_schema_is_valid_json(self):
        dumped = json.dumps(prompts.TRIAGE_RESPONSE_SCHEMA)
        parsed = json.loads(dumped)
        assert "findings" in parsed["properties"]

    def test_deep_schema_includes_fix_suggestion(self):
        item_props = prompts.DEEP_ANALYSIS_RESPONSE_SCHEMA["properties"]["findings"][
            "items"
        ]["properties"]
        assert "fix_suggestion" in item_props
