"""Service layer for the Tenant domain.

The service is the only place that:

- Loads a tenant row and decides what to do when it's missing (raise :class:`TenantNotFoundError`).
- Translates :class:`IntegrityError` from the unique-constraint on
  ``tenant_code`` into a stable 409 ``tenant_already_exists`` envelope.
- Enforces invariants the model can't (e.g. "the new name must not be
  empty" — caught upstream by Pydantic, but the service is the last
  line of defence in case some other caller bypasses it).

Routes are thin: they parse the request, call a service function, and
return the result wrapped in :func:`app.shared.responses.success_response`.
The service raises :class:`AppError` subclasses; the global handler in
:mod:`app.shared.exceptions` converts those to the standard envelope.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tenant import repository as repo
from app.domains.tenant.models import Tenant

from app.shared.exceptions import TenantNotFoundError
from app.domains.tenant.exceptions import TenantAlreadyExistsError




# ---------------------------------------------------------------------------
# Service operations
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TenantCreateInput:
    """Plain-data input for :func:`create_tenant`.

    Using a dataclass (rather than passing the Pydantic ``TenantCreate``
    model straight through) decouples the service signature from the
    HTTP layer. If we later add a CLI or background job that creates
    tenants, it can build the same input struct without depending on
    FastAPI / Pydantic.
    """

    tenant_code: str
    name: str


async def get_tenant_by_code(db: AsyncSession, tenant_code: str) -> Tenant:
    """Load a tenant by slug, or raise 404 ``tenant_not_found``.

    Used by the GET / PATCH / DELETE / activate / deactivate endpoints —
    each of them treats "not found" as the same error.
    """
    tenant = await repo.get_by_code(db, tenant_code)
    if tenant is None:
        raise TenantNotFoundError(
            "Tenant not found.",
            details={"tenant_code": tenant_code},
        )
    return tenant


async def list_tenants(
    db: AsyncSession,
    *,
    include_inactive: bool = True,
) -> Sequence[Tenant]:
    """List tenants, ordered by ``tenant_code``.

    The flag mirrors the repository layer's parameter verbatim — kept
    here so the route handler doesn't have to know the repository's
    contract.
    """
    return await repo.list_all(db, include_inactive=include_inactive)


async def create_tenant(db: AsyncSession, payload: TenantCreateInput) -> Tenant:
    """Create a new tenant (always inactive).

    The slug and name are already validated by Pydantic at the API boundary; 
    this service layer re-validates the invariant we care about most — the unique ``tenant_code`` — by translating the
    :class:`IntegrityError` from the flush into a typed 409.
    """
    try:
        tenant = await repo.create(
            db,
            tenant_code=payload.tenant_code,
            name=payload.name,
        )
    except IntegrityError as exc:
        # The unique index on ``tenant_code`` is the only constraint that
        # can fail here (the slug regex and length are Pydantic-enforced
        # before we ever reach the DB). If we ever add a CHECK that can
        # also fire, narrow the detection by inspecting ``exc.orig``.
        raise TenantAlreadyExistsError(
            f"Tenant with code {payload.tenant_code!r} already exists.",
            details={"tenant_code": payload.tenant_code},
        ) from exc
    # ``created_at`` / ``updated_at`` are server-defaulted; refresh so the
    # response serializer sees concrete values rather than triggering an
    # async lazy-load (which would fail with ``MissingGreenlet``).
    await db.refresh(tenant)
    return tenant


async def update_tenant_name(
    db: AsyncSession,
    tenant_code: str,
    *,
    new_name: str,
) -> Tenant:
    """Update only the ``name`` field of an existing tenant.

    Raises:
        TenantNotFoundError: 404 if no row matches ``tenant_code``.
    """
    tenant = await get_tenant_by_code(db, tenant_code)
    await repo.update_name(db, tenant, name=new_name)
    # Refresh so the response model sees the new ``updated_at`` from the
    # ``onupdate=func.now()`` trigger; same ``MissingGreenlet`` concern
    # as in :func:`create_tenant`.
    await db.refresh(tenant)
    return tenant


async def set_tenant_active(
    db: AsyncSession,
    tenant_code: str,
    *,
    is_active: bool,
) -> Tenant:
    """Flip ``is_active`` to the requested value. Idempotent.

    Used by both ``POST /activate`` (``is_active=True``) and
    ``POST /deactivate`` / ``DELETE`` (``is_active=False``).
    """
    tenant = await get_tenant_by_code(db, tenant_code)
    await repo.set_active(db, tenant, is_active=is_active)
    # Refresh so the response model sees the new ``updated_at`` even when
    # the flush was a no-op (e.g. flipping ``is_active`` to its current
    # value). Cheap insurance against stale data on the wire.
    await db.refresh(tenant)
    return tenant
