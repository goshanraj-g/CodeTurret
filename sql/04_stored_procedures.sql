-- ============================================================
-- CodeBouncer: Stored Procedures
-- ============================================================

USE DATABASE CODEBOUNCER;
USE SCHEMA CORE;

-- Main scan entry point
CREATE OR REPLACE PROCEDURE RUN_SECURITY_SCAN(
    REPO_NAME VARCHAR DEFAULT NULL,
    SCAN_TYPE VARCHAR DEFAULT 'INCREMENTAL'
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'snowflake-ml-python')
IMPORTS = (
    '@CODEBOUNCER.CORE.BOUNCER_STAGE/bouncer_logic/scanner.py',
    '@CODEBOUNCER.CORE.BOUNCER_STAGE/bouncer_logic/file_reader.py',
    '@CODEBOUNCER.CORE.BOUNCER_STAGE/bouncer_logic/cortex_client.py',
    '@CODEBOUNCER.CORE.BOUNCER_STAGE/bouncer_logic/prompts.py',
    '@CODEBOUNCER.CORE.BOUNCER_STAGE/bouncer_logic/result_formatter.py',
    '@CODEBOUNCER.CORE.BOUNCER_STAGE/bouncer_logic/config.py'
)
HANDLER = 'scanner.run_security_scan';

-- Fetch latest commits from all configured git repos
CREATE OR REPLACE PROCEDURE FETCH_ALL_REPOS()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    ALTER GIT REPOSITORY CODEBOUNCER.INTEGRATIONS.GITHUB_REPO FETCH;
    RETURN 'Fetch complete';
END;
$$;

-- Wrapper that fetches then scans (used by the scheduled task)
CREATE OR REPLACE PROCEDURE SCHEDULED_SCAN_WRAPPER()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    CALL FETCH_ALL_REPOS();
    CALL RUN_SECURITY_SCAN(NULL, 'INCREMENTAL');
    RETURN 'Scheduled scan complete';
END;
$$;
