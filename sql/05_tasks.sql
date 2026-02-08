-- ============================================================
-- CodeBouncer: Scheduled Scanning Task
-- ============================================================

USE DATABASE CODEBOUNCER;
USE SCHEMA CORE;

CREATE OR REPLACE TASK SCHEDULED_SECURITY_SCAN
  WAREHOUSE = CODEBOUNCER_WH
  SCHEDULE  = 'USING CRON 0 * * * * UTC'
AS
  CALL SCHEDULED_SCAN_WRAPPER();

-- Enable the task (requires ACCOUNTADMIN or EXECUTE TASK privilege)
ALTER TASK SCHEDULED_SECURITY_SCAN RESUME;
