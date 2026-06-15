"""Tenant ORM model.

A tenant is an isolated customer of the platform. Every other table carries
a ``tenant_id`` foreign key back to this table. ``tenant_code`` is the
human-readable slug used in URLs and logs; ``id`` (UUID) is the
machine-readable primary key.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        # Slug format: lowercase alphanumeric segments joined by single hyphens.
        # Length 3-32. Mirrored by a Pydantic validator in app/schemas/tenant.py
        # so API callers get a clean 422, with the DB CHECK as a safety net
        # for direct SQL writes.
        CheckConstraint(
            "tenant_code ~ '^[a-z0-9]+(-[a-z0-9]+)*$' "
            "AND char_length(tenant_code) BETWEEN 3 AND 32",
            name="tenant_code_slug_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Surrogate primary key. Used in foreign keys from templates and notifications.",
    )
    tenant_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        doc=(
            "Human-readable slug used in URLs (e.g. /tenants/{tenant_code}) and "
            "logs. Slug format and 3-32 length enforced by a DB CHECK; "
            "Pydantic mirrors the same rule at the API boundary."
        ),
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Display name. Free-form, not used in routing or identification.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc=(
            "Defaults to false on creation. Admin must explicitly activate via "
            "POST /tenants/{tenant_code}/activate. Inactive tenants are "
            "rejected at the API boundary with 403 TENANT_INACTIVE."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Row creation timestamp, set by the database.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last update timestamp, maintained by the database on every UPDATE.",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Tenant id={self.id} code={self.tenant_code!r} active={self.is_active}>"
