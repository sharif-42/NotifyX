"""Header-extraction helpers used by FastAPI dependency functions.

These are thin wrappers around FastAPI's ``Header(...)`` machinery. The
point of having a layer here (rather than calling ``Header(...)``
inline in each dependency) is twofold:

1. **One place to change the header names.** If we later move from
   ``X-Admin-Key`` to ``Authorization: Bearer ...`` (Phase 2), only
   this module changes.
2. **A consistent error path.** A missing or wrong header always raises
   :class:`AuthenticationError` from this module — never ``HTTPException``,
   never a FastAPI default 422. The error envelope stays uniform.

Usage::

    from fastapi import Depends
    from app.core.security import get_admin_key_header

    @router.post(...)
    async def create(payload: ..., admin_key: str = Depends(get_admin_key_header)):
        ...
"""

from __future__ import annotations

from fastapi import Header

from app.shared.exceptions import AuthenticationError


# Header name constants. Kept here so the names live in one place — see
# module docstring point 1.
ADMIN_KEY_HEADER = "X-Admin-Key"
TENANT_ID_HEADER = "X-Tenant-ID"


async def get_admin_key_header(
    x_admin_key: str | None = Header(default=None, alias=ADMIN_KEY_HEADER),
) -> str:
    """Extract the admin key from the request headers.

    Raises:
        AuthenticationError: 401 ``auth_error`` if the header is missing
            or empty. The value is *not* checked here — that's the job
            of :func:`app.core.dependencies.get_admin`, which has access
            to the settings.
    """
    if not x_admin_key or not x_admin_key.strip():
        raise AuthenticationError(f"Missing or empty {ADMIN_KEY_HEADER} header.")
    return x_admin_key.strip()


async def get_tenant_id_header(
    x_tenant_id: str | None = Header(default=None, alias=TENANT_ID_HEADER),
) -> str:
    """Extract the tenant id (UUID) from the request headers.

    Raises:
        AuthenticationError: 401 ``auth_error`` if the header is missing
            or empty. Validity of the UUID and existence / active-status
            of the tenant are checked downstream in
            :func:`app.core.dependencies.get_active_tenant`.
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise AuthenticationError(f"Missing or empty {TENANT_ID_HEADER} header.")
    return x_tenant_id.strip()
