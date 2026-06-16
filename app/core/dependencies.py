"""FastAPI dependency functions for auth, DB session, and active-tenant lookup.

Layering: this module is the *only* place that depends on
:mod:`app.core.security` (header extraction) and :mod:`app.core.database`
(DB session). Route handlers import from here — never from
:mod:`app.core.security` directly, never from :mod:`app.core.database`
directly. That keeps the auth flow greppable in one file.

The three dependencies:

- :func:`get_db` — yields an :class:`AsyncSession` per request. Re-exported
  from :mod:`app.core.database` for ergonomic imports in route signatures.
- :func:`get_admin` — checks ``X-Admin-Key`` (extracted by
  :func:`app.core.security.get_admin_key_header`) against
  ``settings.admin_api_key``. Used on tenant-CRUD routes.
- :func:`get_active_tenant` — checks ``X-Tenant-ID`` (extracted by
  :func:`app.core.security.get_tenant_id_header`), looks up the tenant
  in the DB, verifies ``is_active``. Used on every tenant-scoped route
  (templates, notifications, etc.).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, get_db
from app.core.security import (
    get_admin_key_header, 
    get_tenant_id_header
)
from app.domains.tenant.models import Tenant
from app.shared.exceptions import (
    AuthenticationError,
    TenantInactiveError,
    TenantNotFoundError,
)


# Re-export so route handlers can write
# ``db: AsyncSession = Depends(get_db)`` from this module alone.
__all__ = [
    "get_db",
    "get_admin",
    "get_active_tenant",
]


# ---------------------------------------------------------------------------
# get_db — re-exported from app.core.database
# ---------------------------------------------------------------------------
# We don't redefine it here; the canonical implementation lives next to
# the engine so the two stay co-located. Importing it under the same name
# in this module lets routes have a single import line.


# ---------------------------------------------------------------------------
# get_admin — admin-key auth
# ---------------------------------------------------------------------------


async def get_admin(
    admin_key: Annotated[str, Depends(get_admin_key_header)],
) -> str:
    """Verify the supplied admin key against ``settings.admin_api_key``.

    Returns the verified key on success. Raises
    :class:`AuthenticationError` (401 ``auth_error``) on mismatch.

    Used on tenant CRUD endpoints (Step 8).
    """
    if admin_key != settings.admin_api_key:
        raise AuthenticationError("Invalid admin key.")
    return admin_key


# ---------------------------------------------------------------------------
# get_active_tenant — X-Tenant-ID + DB lookup + is_active check
# ---------------------------------------------------------------------------


async def get_active_tenant(
    tenant_id_str: Annotated[str, Depends(get_tenant_id_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """Resolve the ``X-Tenant-ID`` header to an active ``Tenant`` row.

    Failure modes (each raises the corresponding :class:`AppError`):

    1. The header isn't a valid UUID → :class:`TenantNotFoundError` (404).
       We treat malformed UUIDs the same as "no such tenant" — there is
       no useful information to leak about *which* tenants exist.
    2. The UUID is well-formed but no row exists → :class:`TenantNotFoundError`.
    3. The row exists but ``is_active=false`` → :class:`TenantInactiveError`
       (403 ``tenant_inactive``).

    Success returns the loaded :class:`Tenant` ORM object, which the
    route can use to scope subsequent queries (``WHERE tenant_id = t.id``).
    """
    try:
        tenant_uuid = uuid.UUID(tenant_id_str)
    except ValueError:
        raise TenantNotFoundError(
            "Tenant not found.", {"tenant_id": tenant_id_str}
        ) from None

    tenant = await db.get(Tenant, tenant_uuid)
    if tenant is None:
        raise TenantNotFoundError(
            "Tenant not found.", {"tenant_id": tenant_id_str}
        )

    if not tenant.is_active:
        raise TenantInactiveError(
            "Tenant is not active.",
            {"tenant_id": str(tenant.id), "tenant_code": tenant.tenant_code},
        )

    return tenant


# ---------------------------------------------------------------------------
# Module-level re-exports for type checkers / IDE auto-import
# ---------------------------------------------------------------------------
# ``async_session_factory`` is imported above so callers (and tests) can
# also reach the raw sessionmaker via this module if they need to. Kept
# un-exported; reach for it via ``app.core.database`` directly when you
# really want it.
_ = async_session_factory  # explicit no-op so the import isn't linted away
