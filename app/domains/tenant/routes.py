"""HTTP routes for the Tenant domain.

All seven endpoints sit behind the :func:`app.core.dependencies.get_admin`
dependency — tenant CRUD is an admin-only surface. Tenant-scoped resources
(templates, notifications) will be added in later steps and use
:func:`get_active_tenant` instead.

Each handler does the minimum the framework requires: extract path / body
params, call the service, wrap the result in :func:`success_response`.
Business rules, 404s, and 409s are raised as :class:`AppError` subclasses
from the service and converted to the standard envelope by the global
handler registered in :mod:`app.main`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_admin, get_db
from app.domains.tenant import service as tenant_service
from app.domains.tenant.schemas import (
    TenantCreate,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)
from app.shared.responses import success_response

# ``tags`` groups the routes under a single heading in the OpenAPI docs.
router = APIRouter(prefix="/tenants", tags=["tenants"])


# ---------------------------------------------------------------------------
# Path-parameter validator
# ---------------------------------------------------------------------------
# FastAPI applies ``Path(...)`` before the request hits the handler body.
# Reusing the same length rule as the schema keeps the URL-space aligned
# with the database CHECK (3-32 chars). The regex itself is only enforced
# at create-time — once a row exists, its slug is canonical.

_TenantCode = Annotated[
    str,
    Path(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="URL-safe slug, lowercase alphanumeric with single hyphens.",
        examples=["acme", "northwind-co"],
    ),
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a tenant (inactive by default)")
async def create_tenant(
    payload: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
) -> JSONResponse:
    """Create a new tenant.

    Tenant will be created with ``is_active=false`` by default; 
    use the activate endpoint to enable it by admin action.
 
    Errors:
        409 ``tenant_already_exists`` — the slug is taken.
        422 ``validation_error`` — the slug regex failed (also enforced
            by the DB CHECK, but rejected here before a round-trip).
    """
    tenant = await tenant_service.create_tenant(
        db,
        tenant_service.TenantCreateInput(
            tenant_code=payload.tenant_code,
            name=payload.name,
        ),
    )
    return success_response(
        data=TenantResponse.model_validate(tenant).model_dump(mode="json"),
        message="Tenant created.",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("", summary="List tenants", status_code=status.HTTP_200_OK)
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
    include_inactive: bool = True,
) -> JSONResponse:
    """Return every tenant ordered by ``tenant_code``.

    Query params:
        include_inactive: when ``false``, only active tenants are returned.
            Defaults to ``true`` so the admin UI sees the full picture.
    """
    tenants = await tenant_service.list_tenants(
        db, include_inactive=include_inactive
    )
    items = [TenantResponse.model_validate(tenant).model_dump(mode="json") for tenant in tenants]
    body = TenantListResponse(items=items, count=len(items))
    return success_response(
        data=body.model_dump(mode="json"),
        message="Tenants listed.",
    )


@router.get("/{tenant_code}", summary="Get a single tenant by slug", status_code=status.HTTP_200_OK)
async def get_tenant(
    tenant_code: _TenantCode,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
) -> JSONResponse:
    """Fetch a tenant by its slug.

    Errors:
        404 ``tenant_not_found`` — no row matches the slug.
    """
    tenant = await tenant_service.get_tenant_by_code(db, tenant_code)
    return success_response(
        data=TenantResponse.model_validate(tenant).model_dump(mode="json"),
        message="Tenant fetched.",
    )


@router.patch("/{tenant_code}", summary="Update the tenant's display name", status_code=status.HTTP_200_OK)
async def update_tenant(
    tenant_code: _TenantCode,
    payload: TenantUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
) -> JSONResponse:
    """Change only the ``name`` field.

    Phase 1 keeps the surface minimal — ``tenant_code`` and ``is_active``
    have their own endpoints (delete / activate / deactivate) and are
    not editable through PATCH.

    Errors:
        404 ``tenant_not_found`` — no row matches the slug.
    """
    tenant = await tenant_service.update_tenant_name(
        db, tenant_code, new_name=payload.name
    )
    return success_response(
        data=TenantResponse.model_validate(tenant).model_dump(mode="json"),
        message="Tenant updated.",
    )


@router.delete("/{tenant_code}", summary="Soft-deactivate a tenant (is_active=false)", status_code=status.HTTP_200_OK)
async def delete_tenant(
    tenant_code: _TenantCode,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
) -> JSONResponse:
    """Alias of ``POST /deactivate`` for RESTful clients.

    No hard delete: the row stays in the table with ``is_active=false``
    so historical notifications / templates can still be traced back
    to the originating tenant. Hard delete would orphan foreign keys
    and lose audit history.

    Errors:
        404 ``tenant_not_found`` — no row matches the slug.
    """
    tenant = await tenant_service.set_tenant_active(
        db, tenant_code, is_active=False
    )
    return success_response(
        data=TenantResponse.model_validate(tenant).model_dump(mode="json"),
        message="Tenant deactivated.",
    )


@router.post("/{tenant_code}/activate", summary="Set is_active=true", status_code=status.HTTP_200_OK)
async def activate_tenant(
    tenant_code: _TenantCode,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
) -> JSONResponse:
    """Idempotently enable a tenant.

    Calling this on an already-active tenant is a no-op (returns 200
    with the current row). Errors:
        404 ``tenant_not_found`` — no row matches the slug.
    """
    tenant = await tenant_service.set_tenant_active(
        db, tenant_code, is_active=True
    )
    return success_response(
        data=TenantResponse.model_validate(tenant).model_dump(mode="json"),
        message="Tenant activated.",
    )


@router.post("/{tenant_code}/deactivate", summary="Set is_active=false")
async def deactivate_tenant(
    tenant_code: _TenantCode,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[str, Depends(get_admin)],
) -> JSONResponse:
    """Idempotently disable a tenant.

    Functionally identical to ``DELETE /v1/tenants/{tenant_code}``;
    kept as a separate route so clients that prefer action-style
    endpoints (and the OpenAPI docs) can read it clearly.

    Errors:
        404 ``tenant_not_found`` — no row matches the slug.
    """
    tenant = await tenant_service.set_tenant_active(
        db, tenant_code, is_active=False
    )
    return success_response(
        data=TenantResponse.model_validate(tenant).model_dump(mode="json"),
        message="Tenant deactivated.",
    )
