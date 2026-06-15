"""Application error hierarchy and global FastAPI exception handlers.

The shape:

- :class:`AppError` is the base. It carries a ``message`` (always) and
  an optional ``details`` dict (carries structured per-error context like
  ``{"missing": ["code"]}``).
- :class:`AppError` subclasses pin a fixed ``status_code`` and ``code``
  on the class. Raise sites use the subclass directly — greping for
  ``raise TenantInactiveError`` jumps to the class definition in this
  file.
- :func:`register_exception_handlers` wires four handlers onto a FastAPI
  app: ``AppError``, ``RequestValidationError``, ``StarletteHTTPException``,
  and a catch-all ``Exception``.

All error responses go through :func:`app.shared.responses.error_response`
so the body shape (``{success, error: {code, message, details}}``) is
identical for every error type.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.responses import error_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Base class for all application errors.

    Subclasses pin ``status_code`` and ``code`` on the class itself;
    instances carry the human-readable ``message`` and an optional
    ``details`` dict for structured context.

    Grep-friendly: the raise site (``raise TenantInactiveError("...")``)
    and the class definition live in the same file, so you can jump
    between them.
    """

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


# ---------------------------------------------------------------------------
# Subclasses — one per documented error code
# ---------------------------------------------------------------------------
# See plan.md, "Error code catalogue". The class name IS the raise-site
# name; the class attribute ``code`` is the stable wire-format string
# tenants see in the response body.


class TenantNotFoundError(AppError):
    """``X-Tenant-ID`` doesn't resolve to a row."""

    status_code = 404
    code = "tenant_not_found"


class TenantInactiveError(AppError):
    """Tenant exists but ``is_active=false``."""

    status_code = 403
    code = "tenant_inactive"


class CrossTenantAccessError(AppError):
    """A resource (template, notification, ...) belongs to a different tenant."""

    status_code = 403
    code = "cross_tenant_access"


class TemplateNotFoundError(AppError):
    """``template_id`` not found (or wrong tenant)."""

    status_code = 404
    code = "template_not_found"


class TemplateChannelMismatchError(AppError):
    """``template.channel`` doesn't match the request's channel."""

    status_code = 422
    code = "template_channel_mismatch"


class MissingTemplateVariableError(AppError):
    """A required ``{{var}}`` in the template wasn't supplied in the payload."""

    status_code = 422
    code = "missing_template_variable"


class RecipientFormatError(AppError):
    """Email regex or E.164 phone validation failed."""

    status_code = 422
    code = "recipient_format_invalid"


class NotificationNotFoundError(AppError):
    """``notification_id`` doesn't resolve to a row for this tenant."""

    status_code = 404
    code = "notification_not_found"


class BrokerUnavailableError(AppError):
    """ARQ enqueue failed. The notification row has been rolled back."""

    status_code = 503
    code = "broker_unavailable"


class AuthenticationError(AppError):
    """Missing or wrong admin key (or tenant header)."""

    status_code = 401
    code = "auth_error"


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Register the four global handlers on a FastAPI app.

    Call this once from ``app/main.py`` during app construction. Calling
    it twice on the same app is harmless — FastAPI's
    ``add_exception_handler`` overwrites the previous registration.
    """

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Any ``AppError`` subclass → its declared status_code and code."""
        level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
        logger.log(
            level,
            "app.error",
            extra={
                "event": "app.error",
                "method": request.method,
                "path": request.url.path,
                "code": exc.code,
                "status_code": exc.status_code,
                "app_message": exc.message,  # renamed: 'message' is a reserved LogRecord attr
            },
        )
        return error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic body/query validation failure → 422 with raw errors in details."""
        logger.warning(
            "validation.error",
            extra={
                "event": "validation.error",
                "method": request.method,
                "path": request.url.path,
            },
        )
        return error_response(
            code="validation_error",
            message="Invalid request payload",
            details=exc.errors(),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Bare ``HTTPException`` (404 unknown route, 405 wrong method) → envelope.

        Our own code never raises these — only FastAPI's built-in
        routing does. Kept consistent with the rest of the envelope.
        """
        level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
        logger.log(
            level,
            "http.error",
            extra={
                "event": "http.error",
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
                "app_detail": str(exc.detail) if exc.detail else None,
            },
        )
        return error_response(
            code="http_error",
            message=str(exc.detail) if exc.detail else "HTTP error.",
            details=None,
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all. Logs full traceback server-side, returns generic 500.

        The actual exception message is intentionally NOT in the response
        — it may leak internals (file paths, SQL fragments, secrets).
        """
        logger.exception(
            "unhandled.exception",
            extra={
                "event": "unhandled.exception",
                "method": request.method,
                "path": request.url.path,
            },
        )
        return error_response(
            code="internal_error",
            message="Internal server error",
            details=None,
            status_code=500,
        )
