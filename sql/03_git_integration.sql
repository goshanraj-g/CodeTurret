-- ============================================================
-- CodeBouncer: Git Integration Setup
-- ============================================================
-- Replace placeholder values before running.

USE DATABASE CODEBOUNCER;
USE SCHEMA INTEGRATIONS;

-- 1. Secret for GitHub authentication
CREATE OR REPLACE SECRET GITHUB_PAT_SECRET
  TYPE = PASSWORD
  USERNAME = '<GITHUB_USERNAME>'
  PASSWORD = '<GITHUB_PERSONAL_ACCESS_TOKEN>';

-- 2. API integration for GitHub HTTPS
CREATE OR REPLACE API INTEGRATION GITHUB_API_INTEGRATION
  API_PROVIDER = git_https_api
  API_ALLOWED_PREFIXES = ('https://github.com/')
  ALLOWED_AUTHENTICATION_SECRETS = ALL
  ENABLED = TRUE;

-- 3. Git repository object (one per monitored repo)
-- Create additional repositories as needed and register them in REPOSITORY_CONFIG.
CREATE OR REPLACE GIT REPOSITORY GITHUB_REPO
  API_INTEGRATION = GITHUB_API_INTEGRATION
  GIT_CREDENTIALS = GITHUB_PAT_SECRET
  ORIGIN = '<REPO_HTTPS_URL>';

-- 4. Initial fetch
ALTER GIT REPOSITORY GITHUB_REPO FETCH;

-- 5. Stage for bouncer logic code (deployed via `snow stage put`)
CREATE STAGE IF NOT EXISTS CODEBOUNCER.CORE.BOUNCER_STAGE;
