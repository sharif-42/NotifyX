"""Top-level v1 router.

Aggregates the per-domain sub-routers and is itself mounted in
:mod:`app.main` with a ``/v1`` prefix. Adding a new resource (templates,
notifications, health, ...) is a matter of importing its router and
including it here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health
from app.domains.tenant import routes as tenant_routes

# Each sub-router declares its own ``prefix`` (e.g. ``/tenants``), so this
# aggregate router stays prefix-less and the version prefix is applied
# exactly once at the app level in ``app.main``.
v1_router = APIRouter()

v1_router.include_router(tenant_routes.router)
v1_router.include_router(health.router)
