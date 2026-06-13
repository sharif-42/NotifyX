import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.shared.responses import error_response, success_response


settings = get_settings()
setup_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Central place for startup/shutdown resources (DB, queue, cache) as the app grows.
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

register_exception_handlers(app)


@app.get("/health/live")
async def health_live() -> JSONResponse:
    """Liveness probe — the process is up. Never touches dependencies."""
    return success_response(
        data={"status": "ok", "service": settings.app_name},
        message="Service is alive",
    )


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    """Readiness probe — the process is up AND its dependencies are reachable.

    Phase 1 only pings the database. Redis and RabbitMQ checks land with the
    workers (Milestone 5) and observability (Milestone 9).
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — readiness must report any failure
        logger.warning("Readiness check failed: %s", exc)
        return error_response(
            code="not_ready",
            message="Service is not ready",
            details={"checks": {"database": f"error: {exc.__class__.__name__}"}},
            status_code=503,
        )

    return success_response(
        data={"status": "ready", "checks": {"database": "ok"}},
        message="Service is ready",
    )


