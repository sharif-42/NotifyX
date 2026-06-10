# NotifyX
A **multi-tenant notification microservice** built with **FastAPI** for SaaS products.  
NotifyX provides a centralized service to send and track notifications across channels, starting with **Email (SendGrid)** and **SMS (Twilio)**.

## Project Description
NotifyX is designed to be the communication backbone for multiple tenant applications.  
Each tenant can manage templates and send notifications through a single API, while the service handles async processing, delivery tracking, and audit-friendly logs.

The MVP focuses on:
- Tenant profile management
- Email template management and rendering
- Notification send API (email + SMS)
- Async worker-based delivery pipeline
- Delivery status tracking (`PENDING`, `QUEUED`, `PROCESSING`, `SENT`, `FAILED`)
- Filterable notification logs

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
                +--------+---------+
                         |
                         v
                +------------------+
                |  PostgreSQL      |
                |  Notifications   |
                +--------+---------+
                         |
                         v
                +------------------+
                | Message Queue    |
                | RabbitMQ/Kafka   |
                +--------+---------+
                         |
          +--------------+--------------+
          |                             |
          v                             v
+----------------+          +----------------+
| Email Worker   |          | SMS Worker     |
+----------------+          +----------------+
```

## Core Tech Stack
- **Backend API:** FastAPI
- **Database:** PostgreSQL
- **Queue / Async Processing:** RabbitMQ or Kafka (planned queue layer)
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

## Logging
Logging is configured centrally in `app/core/logging.py`.
The app writes structured console logs with timestamp, level, module name, and message, and `LOG_LEVEL` controls verbosity.

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
python -m compileall app
```

### 4) Run API server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 5) Check health endpoint
```bash
curl http://127.0.0.1:8001/health
```
