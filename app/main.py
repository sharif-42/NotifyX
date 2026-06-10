from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.shared.responses import success_response


settings = get_settings()
setup_logging(settings.log_level)


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


@app.get("/health")
async def health() -> JSONResponse:
    return success_response(
        data={"status": "ok", "service": settings.app_name},
        message="Service is healthy",
    )

