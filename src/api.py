"""FastAPI backend for RepoSentinel (CodeBouncer)."""

import logging
import os
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from bouncer_logic import config, scanner

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

class RepoConfig(BaseModel):
    repo_id: int
    repo_name: str
    repo_url: str

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
    try:
        logger.info(f"Starting scan for {request.repo_url} (Deep: {request.deep_scan})")
        
        # Run the existing scanner logic
        # Note: This is synchronous and blocking. For a real prod app, 
        # this should be offloaded to a background task (Celery/RQ).
        result = scanner.run_security_scan(
            repo_url=request.repo_url,
            repo_name=request.repo_name,
            deep_scan=request.deep_scan
        )
        
        return result
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/repos")
def list_repos():
    """List configured repositories."""
    conn = get_snowflake_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT REPO_ID, REPO_NAME, REPO_URL FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG WHERE IS_ACTIVE = TRUE"
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
    conn = get_snowflake_conn()
    try:
        cur = conn.cursor()
        # Join with Repo Config to get names
        cur.execute(
            f"""
            SELECT S.SCAN_ID, S.STATUS, S.STARTED_AT, S.FINDINGS_COUNT, R.REPO_NAME
            FROM CODEBOUNCER.CORE.SCAN_HISTORY S
            JOIN CODEBOUNCER.CORE.REPOSITORY_CONFIG R ON S.REPO_ID = R.REPO_ID
            ORDER BY S.STARTED_AT DESC
            LIMIT {limit}
            """
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
            """
            SELECT *
            FROM CODEBOUNCER.CORE.SCAN_RESULTS
            WHERE SCAN_ID = %s
            """,
            (scan_id,)
        )
        findings = []
        columns = [desc[0].lower() for desc in cur.description]
        for row in cur.fetchall():
            findings.append(dict(zip(columns, row)))
        return findings
    finally:
        conn.close()
