"""Configuration constants for CodeBouncer."""

import os
from enum import Enum

import snowflake.connector


SCANNABLE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx"}

# Gemini models (called via Google AI API)
MODEL_FLASH = "gemini-2.0-flash"
MODEL_PRO = "gemini-2.5-pro"

# Snowflake Cortex model (for post-scan analytics + repo Q&A)
CORTEX_ANALYTICS_MODEL = "llama3.1-8b"
CORTEX_CHAT_MODEL = "llama3.1-8b"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Findings from flash below this confidence trigger a pro re-scan
DEEP_SCAN_THRESHOLD = 0.7

# Truncate files beyond this size to stay within token limits
MAX_FILE_SIZE = 50_000

# Git history analysis
GIT_CLONE_DEPTH = 50
GIT_MAX_COMMITS = 50
GIT_HOT_FILE_BONUS = 1        # +1 risk if changed >= 3 times recently
GIT_SECURITY_COMMIT_BONUS = 2 # +2 risk if touched by security-related commit
GIT_HOT_FILE_THRESHOLD = 3    # min changes to count as "hot"

# Maximum files to scan (after prioritization)
MAX_SCAN_FILES = 25

# Gemini call settings
GEMINI_TIMEOUT_SECONDS = 60
GEMINI_MAX_RETRIES = 2
GEMINI_RETRY_DELAY_SECONDS = 2
GEMINI_RATE_LIMIT_DELAY = 7  # seconds between API calls (free tier: 10 req/min)

# Fully-qualified table names
TABLE_SCAN_RESULTS = "CODEBOUNCER.CORE.SCAN_RESULTS"
TABLE_SCAN_HISTORY = "CODEBOUNCER.CORE.SCAN_HISTORY"
TABLE_REPO_CONFIG = "CODEBOUNCER.CORE.REPOSITORY_CONFIG"


def get_snowflake_connection():
    """Create a Snowflake connection from environment variables."""
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "CODEBOUNCER_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "CODEBOUNCER"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "CORE"),
    )
