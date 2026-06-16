"""Pydantic schemas for the Tenant resource.

Layering: the service layer raises ``AppError`` subclasses on bad input;
this module is purely the request/response shape that crosses the wire.

The slug format constraint on ``tenant_code`` is enforced here via a
Pydantic ``field_validator`` matching the DB CHECK in
:mod:`app.domains.tenant.models`:

    regex:  ``^[a-z0-9]+(-[a-z0-9]+)*$``
    length: 3-32

The DB CHECK is the safety net for direct SQL writes; the validator gives
API callers a clean 422 with a structured error before the request
reaches the database.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.constants import TENANT_CODE_RE


# Tanant name is free-form, but we still want a reasonable upper bound to
_TENANT_NAME_MAX_LEN = 255


# ---------------------------------------------------------------------------
#                               Request bodies                              #
# ---------------------------------------------------------------------------

class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_code: str = Field(
        ...,
        min_length=3,
        max_length=32,
        description="URL-safe slug. Lowercase alphanumeric, single hyphens, 3-32 chars.",
        examples=["acme", "northwind-co"],
    )
    name: str = Field(
        ...,
        min_length=3,
        max_length=_TENANT_NAME_MAX_LEN,
        description="Display name. Free-form.",
        examples=["Acme Corporation"],
    )
    @field_validator("tenant_code")
    @classmethod
    def _validate_tenant_code(cls, value: str) -> str:
        """Enforce the slug regex (mirrors the DB CHECK).

        Raises:
            ValueError: 422 ``validation_error`` with the field path set
                to ``tenant_code`` so the caller knows which field failed.
        """
        if not TENANT_CODE_RE.match(value):
            raise ValueError(
                "tenant_code must match ^[a-z0-9]+(-[a-z0-9]+)*$ "
                "(lowercase alphanumeric segments joined by single hyphens)."
            )
        return value


class TenantUpdate(BaseModel):
    """Body for ``PATCH /v1/tenants/{tenant_code}``.

    Phase 1: only ``name`` is editable. ``tenant_code`` is the immutable
    slug used in URLs and foreign keys; ``is_active`` has its own dedicated
    endpoints (activate / deactivate / delete). Phase 2 may extend this
    model as additional mutable fields are added.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=3,
        max_length=_TENANT_NAME_MAX_LEN,
        description="New display name.",
    )


# ---------------------------------------------------------------------------
#                               Response bodies                             #
# ---------------------------------------------------------------------------


class TenantResponse(BaseModel):
    """Wire shape for a single tenant.

    Mirrors the ORM row 1:1; we serialize ``id`` and timestamps as strings
    to keep the JSON output stable and language-agnostic (UUIDs, ISO-8601
    timestamps with timezone).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantListResponse(BaseModel):
    """Wire shape for ``GET /v1/tenants``.

    Wrapped in a list rather than a bare array so we can extend with
    pagination / cursor metadata in Phase 2 without breaking clients.
    """

    items: list[TenantResponse]
    count: int = Field(..., description="Number of items in this page.")
