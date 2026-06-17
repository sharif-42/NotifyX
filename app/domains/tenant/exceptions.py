from fastapi import status

from app.shared.exceptions import AppError


class TenantAlreadyExistsError(AppError):
    """A tenant with the given ``tenant_code`` is already present.

    Status 409 (``Conflict``) with the wire code ``tenant_already_exists``.
    Defined here rather than in :mod:`app.shared.exceptions` because it's
    the only place that knows about tenant uniqueness; if a future
    resource needs the same envelope shape, this can move to the shared
    module.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "tenant_already_exists_with_the_provided_tenant_code"