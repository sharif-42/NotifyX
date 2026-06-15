"""Application settings, loaded from environment variables / .env file.

Single source of truth for runtime configuration. ``alembic/env.py`` and
the ARQ worker both import from here so the connection strings and
credentials live in one place.

All fields are required unless they have a default — Pydantic validates
on instantiation and any missing required value raises a clear
``ValidationError`` at import time. Fail-fast: the process exits
immediately rather than crashing on first use of a config value.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.constants import APP_NAME, APP_VERSION, Environment


class Settings(BaseSettings):
    """Application configuration. Values come from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- App metadata --------------------------------------------------------
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    app_env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"

    # -- Database ------------------------------------------------------------
    # Async driver is required because the SQLAlchemy engine is async.
    # No default: a misconfigured environment (missing DATABASE_URL) must
    # fail at import time, not on first request.
    database_url: str = Field(
        description="PostgreSQL connection string. Must use the asyncpg driver.",
    )

    # -- Redis / ARQ broker --------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string used as the ARQ broker.",
    )

    # -- Email provider (SendGrid) -------------------------------------------
    sendgrid_api_key: str = Field(
        default="",
        description="SendGrid API key. Empty string allowed in dev with mock senders.",
    )
    sendgrid_from_email: str = Field(
        default="noreply@example.com",
        description="Default From: address for outbound email.",
    )

    # -- SMS provider (Twilio) -----------------------------------------------
    twilio_account_sid: str = Field(
        default="",
        description="Twilio account SID. Empty string allowed in dev with mock senders.",
    )
    twilio_auth_token: str = Field(
        default="",
        description="Twilio auth token. Empty string allowed in dev with mock senders.",
    )
    twilio_from_phone: str = Field(
        default="+15005550006",
        description="Twilio sender phone in E.164 format.",
    )

    # -- Admin auth ----------------------------------------------------------
    # Used for tenant CRUD endpoints. Sent by the caller as the X-Admin-Key
    # header. Phase 2 replaces this with a per-tenant API key system.
    admin_api_key: str = Field(
        default="dev-admin-key",
        description="Shared secret for tenant CRUD endpoints. Sent as X-Admin-Key.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    Cached so repeated imports don't re-read / re-parse ``.env``. The
    first call is the only one that hits the filesystem; subsequent
    calls return the same object.
    """
    return Settings()


# Module-level singleton. This is what every other module imports
# (``from app.core.config import settings``). Reading ``.env`` happens
# exactly once on first import — fail-fast if it's missing required
# values, since by the time anyone is holding a reference to this
# object, the process is already configured correctly.
settings: Settings = get_settings()
