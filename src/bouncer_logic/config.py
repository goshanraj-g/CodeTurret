"""Configuration constants for CodeBouncer."""

from enum import Enum


SCANNABLE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx"}

MODEL_FLASH = "gemini-3.0-flash"
MODEL_PRO = "gemini-3.0-pro"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Findings from flash below this confidence trigger a pro re-scan
DEEP_SCAN_THRESHOLD = 0.7

# Truncate files beyond this size to stay within token limits
MAX_FILE_SIZE = 50_000

# Fully-qualified table names
TABLE_SCAN_RESULTS = "CODEBOUNCER.CORE.SCAN_RESULTS"
TABLE_SCAN_HISTORY = "CODEBOUNCER.CORE.SCAN_HISTORY"
TABLE_REPO_CONFIG = "CODEBOUNCER.CORE.REPOSITORY_CONFIG"
