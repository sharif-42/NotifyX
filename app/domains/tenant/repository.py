"""Repository layer for the Tenant domain.

Thin async wrappers over SQLAlchemy queries. Routes call the service, the
service calls this module. No business rules, no exception translation
beyond what SQLAlchemy raises naturally — those are handled in the
service layer.

Every function takes an :class:`AsyncSession` as its first argument (the
service obtains it via the ``get_db`` FastAPI dependency). The repository
never creates or commits a session of its own.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tenant.models import Tenant


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def get_by_id(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    """Load a tenant by primary key. Returns ``None`` if not found."""
    return await db.get(Tenant, tenant_id)


async def get_by_code(db: AsyncSession, tenant_code: str) -> Tenant | None:
    """Load a tenant by its slug. Returns ``None`` if not found.

    Case-sensitive: the DB CHECK restricts ``tenant_code`` to lowercase,
    so two callers asking for ``"Acme"`` vs ``"acme"`` see different
    results. That's the right behaviour — the slug is meant to be
    canonical, and the API layer's Pydantic validator already rejects
    uppercase input at the boundary.
    """
    stmt = select(Tenant).where(Tenant.tenant_code == tenant_code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_all(
    db: AsyncSession,
    *,
    include_inactive: bool = True,
) -> Sequence[Tenant]:
    """Return all tenants, ordered by ``created_at`` for stable output.

    Args:
        include_inactive: When 'False', only active tenants are returned. 
        Phase 1 admin UI lists every tenant (active and inactive) by default, so this defaults to 'True'.
    """
    stmt = select(Tenant).order_by(Tenant.created_at)
    if not include_inactive:
        stmt = stmt.where(Tenant.is_active.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


async def create(
    db: AsyncSession,
    *,
    tenant_code: str,
    name: str,
) -> Tenant:
    """Insert a new tenant row.

    The new row is always created with is_active=False. 
    The model has server_default="false", so we don't pass it here.

    Raises:
        IntegrityError: The 'tenant_code' already exists (unique constraint). The service layer translates this to a 409.
    """
    tenant = Tenant(tenant_code=tenant_code, name=name)
    db.add(tenant)
    try:
        await db.flush()
    except IntegrityError:
        # Roll back the failed insert so the session is usable for a subsequent retry. 
        # The caller (service) decides whether to surface a 409 or retry.
        await db.rollback()
        raise
    return tenant


async def update_name(db: AsyncSession, tenant: Tenant, *, name: str) -> None:
    """Update only the ``name`` field. Caller is responsible for the load.

    We mutate the ORM object directly and let 'get_db' commit at the end of the request. 
    no explicit commit here. 'updated_at' is advanced by the 'onupdate=func.now()' clause on the column.
    """
    tenant.name = name
    await db.flush()


async def set_active(db: AsyncSession, tenant: Tenant, *, is_active: bool) -> None:
    """Flip ``is_active`` to the given value. No-op if already in that state.

    Idempotent: calling ``set_active(True)`` on an already-active tenant
    is a no-op (no error, no event). The ``updated_at`` column still
    advances on every write because of the ``onupdate`` clause — a
    future optimisation could skip the write when the value hasn't
    changed, but it's not worth the branching in Phase 1.
    """
    tenant.is_active = is_active
    await db.flush()
