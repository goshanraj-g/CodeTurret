"""FastAPI backend for RepoSentinel (CodeBouncer)."""

import logging
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

from bouncer_logic import config, scanner, repo_chat

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RepoSentinel API", version="1.0.0")

# CORS (Allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, allow all. Lock down in prod.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Pydantic Models --

class ScanRequest(BaseModel):
    repo_url: str
    deep_scan: bool = False
    repo_name: Optional[str] = None

class AskRequest(BaseModel):
    repo_name: str
    question: str

# -- Dependency --
def get_snowflake_conn():
    return config.get_snowflake_connection()

# -- Endpoints --

@app.get("/")
def health_check():
    return {"status": "ok", "service": "RepoSentinel API"}

@app.post("/scan")
def trigger_scan(request: ScanRequest):
    """Trigger a security scan."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY environment variable not set"
        )

    try:
        logger.info("Starting scan for %s (Deep: %s)", request.repo_url, request.deep_scan)

        result = scanner.run_security_scan(
            repo_url=request.repo_url,
            repo_name=request.repo_name,
            deep_scan=request.deep_scan
        )

        return result
    except Exception as e:
        logger.error("Scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/repos")
def list_repos():
    """List configured repositories."""
    conn = get_snowflake_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT REPO_ID, REPO_NAME, REPO_URL FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG"
        )
        repos = []
        for row in cur.fetchall():
            repos.append({
                "repo_id": row[0],
                "repo_name": row[1],
                "repo_url": row[2]
            })
        return repos
    finally:
        conn.close()

@app.get("/scans")
def list_recent_scans(limit: int = 10):
    """List recent scan history."""
    limit = min(max(limit, 1), 100)

    conn = get_snowflake_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT S.SCAN_ID, S.STATUS, S.STARTED_AT, S.FINDINGS_COUNT, R.REPO_NAME
               FROM CODEBOUNCER.CORE.SCAN_HISTORY S
               JOIN CODEBOUNCER.CORE.REPOSITORY_CONFIG R ON S.REPO_ID = R.REPO_ID
               ORDER BY S.STARTED_AT DESC
               LIMIT %s""",
            (limit,),
        )
        scans = []
        columns = [desc[0].lower() for desc in cur.description]
        for row in cur.fetchall():
            scans.append(dict(zip(columns, row)))
        return scans
    finally:
        conn.close()

@app.get("/findings/{scan_id}")
def get_scan_findings(scan_id: str):
    """Get findings for a specific scan."""
    conn = get_snowflake_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT FINDING_ID, SCAN_ID, FILE_PATH, LINE_NUMBER,
                      SEVERITY, VULN_TYPE, DESCRIPTION, FIX_SUGGESTION,
                      CODE_SNIPPET, MODEL_USED, CONFIDENCE
               FROM CODEBOUNCER.CORE.SCAN_RESULTS
               WHERE SCAN_ID = %s
               ORDER BY
                 CASE SEVERITY
                   WHEN 'CRITICAL' THEN 1
                   WHEN 'HIGH' THEN 2
                   WHEN 'MEDIUM' THEN 3
                   ELSE 4
                 END,
                 CONFIDENCE DESC""",
            (scan_id,),
        )
        findings = []
        columns = [desc[0].lower() for desc in cur.description]
        for row in cur.fetchall():
            findings.append(dict(zip(columns, row)))
        return findings
    finally:
        conn.close()

@app.post("/ask")
def ask_about_repo(request: AskRequest):
    """Ask a natural language question about a repo's scan results."""
    conn = get_snowflake_conn()
    try:
        answer = repo_chat.ask_about_repo(conn, request.repo_name, request.question)
        return {"answer": answer}
    except repo_chat.RepoChatError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
