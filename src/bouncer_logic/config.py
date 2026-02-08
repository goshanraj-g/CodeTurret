"""Configuration constants for CodeBouncer."""

import os
from enum import Enum

import snowflake.connector


SCANNABLE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx"}

MODEL_FLASH = "llama3.1-8b"
MODEL_PRO = "claude-3-5-sonnet"


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

# Maximum files to send to Cortex (after prioritization)
MAX_SCAN_FILES = 25

# Cortex call settings
CORTEX_TIMEOUT_SECONDS = 60
CORTEX_MAX_RETRIES = 2
CORTEX_RETRY_DELAY_SECONDS = 2

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
