"""Template ORM model.

A template is a named, tenant-scoped message body that can be referenced by
notifications. The ``name`` column is unique per tenant (not globally), so
two tenants can each have a template called "welcome-email" without
collision. The ``channel`` column is VARCHAR; valid values are defined by
the ``Channel`` enum in ``app/channels/__init__.py`` (no DB CHECK — see
that module's docstring for rationale).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_templates_tenant_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Surrogate primary key. Referenced by notifications.template_id.",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Owning tenant. Tenant cannot be hard-deleted while templates exist (RESTRICT).",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc=(
            "Human-readable template name. Unique per tenant (composite UNIQUE "
            "on (tenant_id, name)) so two tenants can each have a 'welcome-email' "
            "without collision. Used in URL paths and tenant dashboards."
        ),
    )
    channel: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc=(
            "Delivery channel this template is bound to. Valid values live in "
            "app.channels.Channel; not DB-CHECKed so new channels can be added "
            "without a migration. Cross-checked at notification create-time: "
            "request.channel must match template.channel."
        ),
    )
    subject: Mapped[str | None] = mapped_column(
        String(998),
        nullable=True,
        doc=(
            "Email subject line, with {{var}} placeholders. NULL for SMS "
            "templates (SMS has no subject). For ad-hoc email sends, the caller "
            "can supply a subject directly without using a template."
        ),
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc=(
            "Message body, with Jinja2 {{var}} placeholders. Sandboxed Jinja2 "
            "is used at render time so tenant-supplied templates cannot leak "
            "data. Declared variables are extracted and validated against the "
            "request payload before rendering."
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
        return f"<Template id={self.id} name={self.name!r} channel={self.channel!r}>"
