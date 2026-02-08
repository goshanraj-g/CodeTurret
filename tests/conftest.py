"""Shared test fixtures for CodeBouncer."""

import sys
import os
from unittest.mock import MagicMock
from types import ModuleType

import pytest

# Ensure the src directory is on the path so bouncer_logic can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Stub out the snowflake SDK so tests run without it installed
_sf = ModuleType("snowflake")
_sf_snowpark = ModuleType("snowflake.snowpark")
_sf_snowpark.Session = MagicMock
_sf_snowpark_context = ModuleType("snowflake.snowpark.context")
_sf_snowpark_context.get_active_session = MagicMock
_sf_snowpark_functions = ModuleType("snowflake.snowpark.functions")
_sf_snowpark_functions.col = MagicMock
_sf_snowpark_functions.lit = MagicMock
_sf_snowpark_functions.current_timestamp = MagicMock
_sf_ml = ModuleType("snowflake.ml")
_sf_ml_python = ModuleType("snowflake.ml.python")

sys.modules.setdefault("snowflake", _sf)
sys.modules.setdefault("snowflake.snowpark", _sf_snowpark)
sys.modules.setdefault("snowflake.snowpark.context", _sf_snowpark_context)
sys.modules.setdefault("snowflake.snowpark.functions", _sf_snowpark_functions)
sys.modules.setdefault("snowflake.ml", _sf_ml)
sys.modules.setdefault("snowflake.ml.python", _sf_ml_python)


@pytest.fixture
def mock_session():
    """A mocked Snowpark Session."""
    session = MagicMock()
    session.sql.return_value.collect.return_value = []
    session.create_dataframe.return_value.write.mode.return_value.save_as_table = MagicMock()
    return session


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
