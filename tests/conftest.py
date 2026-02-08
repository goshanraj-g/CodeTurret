"""Shared test fixtures for CodeBouncer."""

import sys
import os
from unittest.mock import MagicMock
from types import ModuleType

import pytest

# Ensure the src directory is on the path so bouncer_logic can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Stub out snowflake.connector so tests run without it installed
_sf = ModuleType("snowflake")
_sf_connector = ModuleType("snowflake.connector")
_sf_connector.connect = MagicMock()

sys.modules.setdefault("snowflake", _sf)
sys.modules.setdefault("snowflake.connector", _sf_connector)

# Stub out google.genai so tests run without it installed
_google = ModuleType("google")
_google_genai = ModuleType("google.genai")
_google_genai.Client = MagicMock()
_google_genai_types = ModuleType("google.genai.types")
_google_genai_types.GenerateContentConfig = MagicMock()

sys.modules.setdefault("google", _google)
sys.modules.setdefault("google.genai", _google_genai)
sys.modules.setdefault("google.genai.types", _google_genai_types)


@pytest.fixture
def mock_conn():
    """A mocked snowflake.connector connection."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.description = [("RESPONSE",)]
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def sample_triage_response():
    return {
        "findings": [
            {
                "line_number": 5,
                "severity": "HIGH",
                "vuln_type": "SQL Injection",
                "description": "User input concatenated into SQL query without parameterization.",
                "confidence": 0.85,
                "code_snippet": 'query = "SELECT * FROM users WHERE id=" + user_id',
            }
        ],
        "file_risk_score": 0.7,
        "summary": "One SQL injection vulnerability found.",
    }


@pytest.fixture
def sample_deep_response():
    return {
        "findings": [
            {
                "line_number": 5,
                "severity": "HIGH",
                "vuln_type": "SQL Injection",
                "description": "Attacker can inject arbitrary SQL via the user_id parameter.",
                "fix_suggestion": (
                    'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))'
                ),
                "confidence": 0.95,
                "code_snippet": 'query = "SELECT * FROM users WHERE id=" + user_id',
                "attack_vector": "HTTP parameter user_id",
                "cwe_id": "CWE-89",
            }
        ],
        "summary": "Confirmed SQL injection. Parameterized query fix provided.",
    }


@pytest.fixture
def sample_file_content():
    return (
        "import sqlite3\n"
        "\n"
        "def get_user(user_id):\n"
        '    conn = sqlite3.connect("app.db")\n'
        '    query = "SELECT * FROM users WHERE id=" + user_id\n'
        "    return conn.execute(query).fetchone()\n"
    )
