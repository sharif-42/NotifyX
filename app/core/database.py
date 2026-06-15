"""
    SQLAlchemy declarative base with a stable naming convention.

    The naming convention ensures Alembic auto-generates deterministic constraint
    and index names (e.g. ``fk_notifications_template_id_templates``) instead of
    hash-suffixed names that change between machines and produce noisy diffs.
"""
import logging
from collections.abc import AsyncIterator
from typing import Any

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


# Naming convention applied to all constraints, indexes, and sequences.
# Keys are SQLAlchemy constraint kinds; values are Python format strings
# that receive the table name and column list (where applicable).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _create_engine() -> AsyncEngine:
    """Build the async engine. URL comes from settings (validated at import)."""
    return create_async_engine(
        settings.database_url,
        echo=False,  # SQL statement logging is controlled via the sqlalchemy loggers
        pool_pre_ping=True,  # detect dropped connections before using them
    )


engine: AsyncEngine = _create_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,  # explicit flush() only; avoids "phantom" writes appearing in mid-transaction reads
    expire_on_commit=False,  # avoid implicit lazy loads after commit in async context
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an ``AsyncSession`` per request.

    Commits on clean exit, rolls back on exception, always closes the session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


__all__: list[Any] = ["engine", "async_session_factory", "get_db"]