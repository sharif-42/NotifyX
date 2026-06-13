# NotifyX

A **multi-tenant notification microservice** built with **FastAPI** for SaaS products.
NotifyX provides a centralized service to send and track notifications across channels, starting with **Email (SendGrid)** and **SMS (Twilio)**.

## Project Description

NotifyX is designed to be the communication backbone for multiple tenant applications.
Each tenant can manage templates and send notifications through a single API, while the service handles async processing, delivery tracking, and audit-friendly logs.

The MVP focuses on:
- Tenant profile management
- Email template management and rendering
- Notification send API (email + SMS) — direct or template-driven
- Async worker-based delivery pipeline using the **outbox pattern**
- Delivery status tracking (`PENDING`, `PROCESSING`, `RETRYING`, `SENT`, `FAILED`)
- Filterable notification logs

## Status Lifecycle

```text
                    PENDING  (API created)
                       |
                       v
                    PROCESSING  (dispatcher pickup)
                    /    |    \
                   /     |     \
            SENT       RETRYING  FAILED
            (terminal)  |        (terminal)
                       |
                       v
                    PROCESSING  (retry pickup, attempt_count++)
                       |
                       ... (SENT, RETRYING, or FAILED)
```

Rules:
- **API commit** — the row is inserted as `PENDING` in the same transaction as the outbox row (Step 4)
- **Dispatcher pickup** — the channel dispatcher flips the row to `PROCESSING` before calling the provider (Step 5)
- **Provider success** → `SENT`; `sent_at` is set, `external_message_id` is captured
- **Provider permanent failure** → `FAILED`; `failure_reason` is set, terminal
- **Provider transient failure** → `RETRYING`; a `retry_jobs` row is scheduled with `next_retry_at`
- **Retry pickup** — the retry worker re-flips to `PROCESSING` (with `attempt_count` incremented) and re-dispatches
- **Retry exhaustion** — after max 3 attempts, the row moves to `FAILED`, the `retry_jobs` row is deleted

The full table of allowed values is enforced at the DB level by the `ck_notifications_status` CHECK constraint: `('PENDING', 'QUEUED', 'PROCESSING', 'RETRYING', 'SENT', 'FAILED')`. `QUEUED` is reserved for a possible future "broker confirmed, not yet picked up" state and is not used in Phase 1. The API does **not** introduce an intermediate queued status — notifications go `PENDING → PROCESSING` directly when a worker actually picks the job up.

## Data Model

```mermaid
erDiagram
    tenants ||--o{ templates : "owns"
    tenants ||--o{ notifications : "owns"
    tenants ||--o{ api_keys : "has (Phase 2)"
    tenants ||--o{ webhooks : "has (Phase 2)"

    templates ||--o{ notifications : "used by (nullable)"

    notifications ||--o{ notification_attempts : "has"
    notifications ||--o{ outbox : "dispatched via"
    notifications ||--o{ retry_jobs : "scheduled for"

    tenants {
        uuid id PK
        string name
        string contact_email
        enum status
        enum plan
        jsonb email_limit_config
        jsonb sms_limit_config
        timestamptz created_at
        timestamptz updated_at
    }

    templates {
        uuid id PK
        uuid tenant_id FK
        string name
        enum channel
        text subject_template
        text body_template
        jsonb variables_schema
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }

    notifications {
        uuid id PK
        uuid tenant_id FK
        uuid template_id FK
        enum type
        string to_address
        text subject
        text message
        jsonb template_variables
        string provider
        enum status
        int attempt_count
        string external_message_id
        text failure_reason
        timestamptz created_at
        timestamptz updated_at
        timestamptz sent_at
    }

    notification_attempts {
        uuid id PK
        uuid notification_id FK
        int attempt_number
        string provider
        enum status
        text error_message
        jsonb request_payload
        jsonb response_payload
        timestamptz created_at
    }

    outbox {
        uuid id PK
        uuid notification_id FK
        enum channel
        jsonb payload
        timestamptz created_at
        timestamptz published_at
    }

    retry_jobs {
        uuid id PK
        uuid notification_id FK
        int attempt_number
        timestamptz next_retry_at
        enum status
        text last_error
        jsonb payload
        timestamptz created_at
        timestamptz updated_at
    }

    api_keys {
        uuid id PK
        uuid tenant_id FK
    }

    webhooks {
        uuid id PK
        uuid tenant_id FK
    }
```

The full per-column reference (types, nullability, defaults, indexes, poller queries, dedup safety net) lives in [`model_summary.md`](./model_summary.md). The four relationships to remember:

- `tenants` is the root — every other row is scoped to a tenant via a `tenant_id` FK
- `notifications.template_id` is **nullable** — direct sends have no template, template-driven sends reference one
- `notifications` is the **center of gravity** for the async pipeline — it has three child tables (`notification_attempts`, `outbox`, `retry_jobs`) that all FK back to it
- `templates.channel` is currently always `EMAIL`; `notifications.type` and `outbox.channel` are both constrained to `EMAIL` or `SMS`

## MVP Architecture (Phase 1)

```text
                +------------------+
                | Client Services  |
                +--------+---------+
                         |
                         v
                +------------------+
                | Notification API |
                |     (FastAPI)    |
                |  (render + outbox|
                |   insert in one  |
                |   transaction)   |
                +--------+---------+
                         |
                         v
                +------------------+
                |  PostgreSQL      |
                |  notifications   |
                |  outbox          |
                |  retry_jobs      |
                |  attempts        |
                +--------+---------+
                         |
            +------------+--------------+
            |                           |
            v                           v
   +------------------+        +------------------+
   |  Outbox Worker   |        |  Retry Worker    |
   |  (poll + publish)|        |  (poll + redrive)|
   +--------+---------+        +--------+---------+
            |                            |
            v                            v
   +------------------+        +------------------+
   | RabbitMQ         |        |  (direct re-     |
   | .email / .sms    |        |   dispatch into  |
   +----+--------+----+        |   dispatcher)    |
        |        |             +------------------+
        v        v
   +--------+ +--------+
   | Email  | | SMS    |
   |Dispatch| |Dispatch|
   | (base) | | (base) |
   +----+---+ +----+---+
        |        |
        v        v
    SendGrid   Twilio
```

Key properties:
- **At-least-once publish** from the outbox; the unique constraint on `notification_attempts(notification_id, attempt_number)` is the dedup safety net.
- **Per-channel queues** (`notifications.email`, `notifications.sms`) with a **shared `BaseDispatcher`** that channel-specific subclasses extend only for the provider call.
- **Retry classification in the provider adapter** — SendGrid: 5xx/429 transient, 4xx permanent. Twilio: 5xx/timeout transient, specific error codes permanent.

## Core Tech Stack
- **Backend API:** FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Queue / Async Processing:** RabbitMQ (per-channel queues)
- **Cache / Infra:** Redis
- **Email Provider:** SendGrid
- **SMS Provider:** Twilio

## Configuration

NotifyX uses `pydantic-settings` in `app/core/config.py` to load settings from environment variables and `.env`.
`get_settings()` caches the parsed settings so the app reuses a single configuration instance.

Example `.env`:
```env
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/notifyx
```

## Response Shape

All API responses follow a standard envelope:

**Success:**
```json
{ "success": true, "message": "...", "data": { ... } }
```

**Error:**
```json
{ "success": false, "error": { "code": "...", "message": "...", "details": ... } }
```

**Submission (`POST /v1/notifications/send`)** returns HTTP 202 with:
```json
{ "id": "...", "status": "PENDING", "request_id": "...", "created_at": "..." }
```

`request_id` is server-generated per request, echoed in the response, and included in every log line that touches the request. This is the foundation for Phase 2 idempotency.

## Health Checks

The service exposes two probe endpoints, matching the orchestrator contract from `plan.md` (Milestone 8):

- `GET /health/live` — **liveness**. Always returns 200 as long as the process is up. Never touches dependencies, so it's cheap and safe to probe aggressively.
- `GET /health/ready` — **readiness**. Pings downstream dependencies (PostgreSQL in Phase 1) and returns 200 with `checks: {database: "ok"}` when everything is reachable, or 503 with the failing check details when something is down.

Both responses use the standard envelope from the next section. Phase 1 only checks the database; Step 8/9 will extend readiness to Redis and RabbitMQ as those come online.

---

## Tenant Isolation (Phase 1)

`tenant_id` is **explicit on every endpoint** and is the **first argument of every service function**. Service signatures follow the pattern `def list_for_tenant(db, tenant_id, ...)`. No `ContextVar` or SQLAlchemy event listeners are used in Phase 1; Phase 2 will introduce a `TenantContext` object resolved from API key auth.

## Logging

Logging is configured centrally in `app/core/logging.py`.
The app writes structured console logs with timestamp, level, module name, and message, and `LOG_LEVEL` controls verbosity.
A JSON formatter is also available — `setup_logging(level, json=True)` emits one JSON object per record (keys: `ts`, `level`, `logger`, `message`) and merges any `extra={...}` fields passed to the logger at the top level, so `request_id`, `tenant_id`, and `notification_id` can be attached per call. Step 9 will wire this on by default.

## Exception Handling

Global exception handlers live in `app/core/exceptions.py`.

| Exception Type | Purpose |
|---|---|
| `AppException` | Custom application/business error with controlled `code`, `message`, and `status_code` |
| `RequestValidationError` | Raised automatically when request data does not match the expected schema |
| `StarletteHTTPException` | Handles framework or explicit HTTP errors such as 404, 405, or raised `HTTPException` |
| `Exception` | Final fallback for unexpected server-side errors; logs traceback and returns a safe 500 response |

## Local Run Commands

### 1) Activate virtual environment
```bash
source venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Optional quick syntax check
```bash
python -m compileall app migrations
```

### 4) Run database migrations
```bash
alembic upgrade head
```

### 5) Run API server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 6) Check health endpoint
```bash
curl http://127.0.0.1:8001/health/live
```

## Phase Plan Summary

**Phase 1 (MVP):** Tenants, templates, notification submit (outbox), per-channel workers, SendGrid + Twilio adapters, retry poller, log APIs, health checks.

**Phase 2:** API key auth + `TenantContext` refactor, quota enforcement, idempotency keys, provider idempotency keys.

**Phase 3+:** Push notifications, webhooks for delivery status callbacks.
