# CodeTurret — Java/Spring Boot Refactor Design

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Full backend rewrite from Python/FastAPI + Snowflake to Java 21/Spring Boot 3.3 + PostgreSQL, with RabbitMQ async pipeline, SSE real-time progress, and Auto-Fix PR generation.

---

## 1. Goals

- Replace the synchronous Python/FastAPI backend with a non-blocking Java/Spring Boot backend
- Use RabbitMQ to decouple scan submission from scan execution (jobs survive restarts, workers scale independently)
- Stream real-time scan progress to the Next.js frontend via Server-Sent Events (SSE)
- Implement the **Auto-Fix PR** feature: AI-generated patches pushed as a GitHub PR via PAT auth
- Replace Snowflake with PostgreSQL (simpler, cheaper, native Spring Data JPA support)
- Keep the existing Next.js frontend; update it to consume SSE and show real-time progress + PR results

---

## 2. Architecture Overview

```
Next.js Frontend
    │
    ├── POST /api/scan              → ScanController     → [scan.requests queue]
    ├── GET  /api/scans/{id}/stream → SseController      ← [scan.progress exchange]
    ├── GET  /api/scans             → ScanController     → PostgreSQL
    ├── GET  /api/findings/{scanId} → FindingController  → PostgreSQL
    ├── CRUD /api/repos             → RepoController     → PostgreSQL
    └── POST /api/ask               → AskController      → GeminiService (Q&A over findings)

RabbitMQ
    ├── scan.requests  (direct exchange, durable queue)  → ScanWorker
    ├── fix.requests   (direct exchange, durable queue)  → FixWorker
    └── scan.progress  (topic exchange)                  → SseController (per-scanId)

ScanWorker (@RabbitListener)
    ├── GitService              (clone repo, hot files, blame, security commits)
    ├── CodeExtractorService    (extract security-relevant snippets)
    ├── RiskAssessorService     (git-boosted file prioritization)
    ├── GeminiService           (flash triage → pro deep analysis)
    ├── FindingRepository       (persist findings to PostgreSQL)
    └── ProgressPublisher       (emit FILE_SCANNED / SCAN_COMPLETE events)

FixWorker (@RabbitListener)  [triggered by user action, not automatic]
    ├── GeminiService           (generate patched file content per finding)
    ├── AutoFixService          (batch fixes per file, resolve multi-finding conflicts)
    ├── GitHubService           (create branch, push files, open PR via GitHub REST API)
    ├── FixPrRepository         (persist PR record to PostgreSQL)
    └── ProgressPublisher       (emit FILE_FIXED / PR_CREATED events)

PostgreSQL (Spring Data JPA)
    ├── repositories
    ├── scans
    ├── findings
    └── fix_prs
```

---

## 3. Data Model

### `repositories`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR | |
| url | VARCHAR | |
| github_token | VARCHAR | AES-encrypted at rest |
| created_at | TIMESTAMP | |

### `scans`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | returned immediately on POST /api/scan |
| repo_id | UUID FK | |
| status | VARCHAR | QUEUED \| RUNNING \| COMPLETED \| FAILED |
| scan_type | VARCHAR | FULL \| DEEP |
| total_files | INT | |
| findings_count | INT | |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |
| error_message | TEXT | |

### `findings`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| scan_id | UUID FK | |
| repo_id | UUID FK | |
| file_path | VARCHAR | |
| line_number | INT | |
| severity | VARCHAR | CRITICAL \| HIGH \| MEDIUM \| LOW |
| vuln_type | VARCHAR | |
| description | TEXT | |
| fix_suggestion | TEXT | |
| code_snippet | TEXT | |
| model_used | VARCHAR | gemini-2.0-flash \| gemini-2.5-pro |
| confidence | FLOAT | |
| commit_hash | VARCHAR | from git blame |
| commit_author | VARCHAR | from git blame |
| commit_date | TIMESTAMP | from git blame |
| created_at | TIMESTAMP | |

### `fix_prs`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| scan_id | UUID FK | |
| pr_url | VARCHAR | GitHub PR URL |
| branch_name | VARCHAR | `codeturret/fix/{scan_id_short}` |
| files_fixed | INT | |
| findings_fixed | INT | |
| status | VARCHAR | OPEN \| MERGED \| CLOSED \| FAILED |
| created_at | TIMESTAMP | |

---

## 4. RabbitMQ Message Flow

### Exchanges & Queues
```
scan.requests  (direct exchange)
  └── scan.queue  (durable)       →  ScanWorker

fix.requests   (direct exchange)
  └── fix.queue   (durable)       →  FixWorker

scan.progress  (topic exchange)
  └── scan.{scanId}.queue (auto-delete, per SSE connection)  →  SseController
```

### Progress Event Schema
All events share this envelope:
```json
{
  "scanId": "uuid",
  "event": "EVENT_TYPE",
  "timestamp": "ISO-8601",
  "data": { }
}
```

| Event | Data payload | Phase |
|---|---|---|
| `SCAN_STARTED` | `{ totalFiles: N }` | Scan |
| `FILE_SCANNED` | `{ file, findings: N, severity: "HIGH" }` | Scan |
| `FILE_SKIPPED` | `{ file, reason }` | Scan |
| `SCAN_COMPLETE` | `{ totalFindings: N }` | Scan |
| `SCAN_FAILED` | `{ error }` | Scan |
| `FIX_STARTED` | `{ filesToFix: N }` | Fix |
| `FILE_FIXED` | `{ file, findingsFixed: N }` | Fix |
| `FIX_FAILED` | `{ file, error }` | Fix |
| `PR_CREATED` | `{ prUrl, branch, filesFixed: N }` | Fix |

### Late-Join Handling
If a frontend client connects to `GET /api/scans/{id}/stream` after the scan has already progressed, the controller reads current scan status from PostgreSQL and emits a synthetic `SCAN_STATUS` seed event containing all progress to date, before forwarding live RabbitMQ events.

---

## 5. Auto-Fix PR Pipeline

Auto-fix is **opt-in**: the scan completes and shows findings first. The user clicks "Generate Fixes" in the UI, which calls `POST /api/scans/{id}/fix`. This enqueues a fix job to `fix.requests`.

### Fix Generation Steps (FixWorker)
1. Load all findings for the scan from PostgreSQL
2. Group findings by `file_path`
3. For each file: fetch current file content from GitHub (`GET /repos/{owner}/{repo}/contents/{path}`), build a single Gemini Pro prompt with all findings for that file, request the corrected full file content
4. Apply fix: `PUT /repos/{owner}/{repo}/contents/{path}` with base64-encoded patched content on branch `codeturret/fix/{scanId[:8]}`
5. After all files: open PR via `POST /repos/{owner}/{repo}/pulls` with body listing each finding fixed (severity, file, vuln type, model used)
6. Persist `fix_prs` record; emit `PR_CREATED` event

### GitHub Authentication
- User provides a GitHub PAT when registering a repo (`POST /api/repos`)
- Token is AES-encrypted (256-bit key from `encryption.secret-key` env var) before DB storage
- Decrypted in memory only at the moment of GitHub API calls in `GitHubService`
- Transmitted over HTTPS only

### Error Handling
- If Gemini fails to generate a valid patch for a file, that file is skipped and `FIX_FAILED` is emitted; other files continue
- If the PR creation fails (e.g. branch already exists), the error is recorded in `fix_prs.status = FAILED` and surfaced in the UI
- Partial fix PRs (some files patched, some skipped) are still opened with a note in the PR body

---

## 6. Project Structure

```
backend/
├── src/main/java/com/codeturret/
│   ├── api/
│   │   ├── ScanController.java
│   │   ├── SseController.java
│   │   ├── FindingController.java
│   │   ├── RepoController.java
│   │   └── AskController.java
│   ├── worker/
│   │   ├── ScanWorker.java
│   │   └── FixWorker.java
│   ├── service/
│   │   ├── GitService.java
│   │   ├── CodeExtractorService.java
│   │   ├── RiskAssessorService.java
│   │   ├── GeminiService.java
│   │   ├── AutoFixService.java
│   │   └── GitHubService.java
│   ├── model/
│   │   ├── Repository.java
│   │   ├── Scan.java
│   │   ├── Finding.java
│   │   └── FixPr.java
│   ├── repository/
│   │   ├── RepositoryRepo.java
│   │   ├── ScanRepo.java
│   │   ├── FindingRepo.java
│   │   └── FixPrRepo.java
│   ├── messaging/
│   │   ├── RabbitConfig.java
│   │   └── ProgressPublisher.java
│   └── config/
│       ├── SecurityConfig.java
│       └── EncryptionConfig.java
├── src/main/resources/
│   └── application.yml
├── docker-compose.yml
└── pom.xml

frontend/                  (existing Next.js — kept as-is except SSE integration)
```

---

## 7. Key Configuration (`application.yml`)

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/codeturret
    username: ${DB_USER}
    password: ${DB_PASSWORD}
  jpa:
    hibernate.ddl-auto: validate
    open-in-view: false
  rabbitmq:
    host: ${RABBITMQ_HOST:localhost}
    port: 5672
    username: ${RABBITMQ_USER:guest}
    password: ${RABBITMQ_PASSWORD:guest}

gemini:
  api-key: ${GEMINI_API_KEY}
  model:
    flash: gemini-2.0-flash
    pro: gemini-2.5-pro
  timeout-seconds: 60
  max-retries: 2
  rate-limit-delay-ms: 7000

github:
  api-url: https://api.github.com

encryption:
  secret-key: ${ENCRYPTION_SECRET_KEY}
```

---

## 8. Local Development

`docker-compose.yml` starts PostgreSQL 16 and RabbitMQ 3.13 (with management UI on port 15672).

```bash
docker-compose up -d
./mvnw spring-boot:run
# frontend
cd frontend && npm run dev
```

Database migrations via Flyway (`src/main/resources/db/migration/`).

---

## 9. Frontend Changes (Next.js)

- `scan/page.tsx`: replace `fetch` polling with `EventSource` on `/api/scans/{id}/stream`; render progress events in `TerminalOutput` in real-time
- `findings/[scanId]/page.tsx`: add "Generate Fixes" button that calls `POST /api/scans/{id}/fix`, then opens a second SSE stream to show fix progress and final PR URL
- No other frontend changes required

---

## 10. Out of Scope

- Scheduled/automatic scanning (can be added later as a cron job triggering `POST /api/scan`)
- Multi-language support beyond `.py .js .ts .tsx .jsx`
- GitHub App authentication (PAT is sufficient for this stage)
- Horizontal worker scaling (run multiple instances of the app consuming from the same RabbitMQ queue — works without changes)
