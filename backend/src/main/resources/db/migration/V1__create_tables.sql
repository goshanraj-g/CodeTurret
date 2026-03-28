-- CodeTurret schema

CREATE TABLE IF NOT EXISTS repositories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL UNIQUE,
    url          VARCHAR(1024) NOT NULL,
    github_token VARCHAR(512),   -- AES-encrypted PAT
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scans (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id        UUID NOT NULL REFERENCES repositories(id),
    status         VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    scan_type      VARCHAR(10) NOT NULL DEFAULT 'FULL',
    total_files    INT NOT NULL DEFAULT 0,
    findings_count INT NOT NULL DEFAULT 0,
    started_at     TIMESTAMP,
    completed_at   TIMESTAMP,
    error_message  TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id        UUID NOT NULL REFERENCES scans(id),
    repo_id        UUID NOT NULL REFERENCES repositories(id),
    file_path      VARCHAR(1024) NOT NULL,
    line_number    INT,
    severity       VARCHAR(10) NOT NULL,
    vuln_type      VARCHAR(128) NOT NULL,
    description    TEXT,
    fix_suggestion TEXT,
    code_snippet   TEXT,
    model_used     VARCHAR(64),
    confidence     FLOAT,
    commit_hash    VARCHAR(40),
    commit_author  VARCHAR(255),
    commit_date    TIMESTAMP,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fix_prs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id        UUID NOT NULL REFERENCES scans(id),
    pr_url         VARCHAR(1024),
    branch_name    VARCHAR(255),
    files_fixed    INT NOT NULL DEFAULT 0,
    findings_fixed INT NOT NULL DEFAULT 0,
    status         VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scans_repo_id    ON scans(repo_id);
CREATE INDEX idx_findings_scan_id ON findings(scan_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_fix_prs_scan_id  ON fix_prs(scan_id);
