"""Notification ORM model.

The central table of the system. Every send request creates one row in
PENDING state; the ARQ worker transitions it to SENT or FAILED.

CHECK constraints enforce:
- Status is one of the three legal values (state machine invariant).
- Recipient fields are consistent with channel: exactly one of
  (recipient_email, recipient_phone) is non-null, matching the channel.

The ``channel`` column itself is NOT constrained at the DB level — valid
values are governed by the ``Channel`` enum in ``app/channels/`` so new
channels can be added without a migration.

A composite index on (tenant_id, status, created_at DESC) supports the
common tenant-scoped status listing query.

``body`` is rendered at enqueue time (in the API service) and stored
alongside the row, so the notification is self-contained for audit even if
the originating template is later edited or deleted.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domains.notification.constants import NotificationStatus


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            f"status IN ('{NotificationStatus.PENDING.value}', '{NotificationStatus.SENT.value}', '{NotificationStatus.FAILED.value}')",
            name="status_valid",
        ),
        CheckConstraint(
            "(channel = 'email' AND recipient_email IS NOT NULL AND recipient_phone IS NULL) "
            "OR (channel = 'sms' AND recipient_phone IS NOT NULL AND recipient_email IS NULL)",
            name="recipient_channel_consistency",
        ),
        Index(
            "ix_notifications_tenant_id_status_created_at",
            "tenant_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Surrogate primary key. Exposed to tenants for status checks.",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Owning tenant. RESTRICT delete: a tenant with notifications cannot be hard-deleted.",
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # If the template is deleted, the notification stays (audit) but loses
        # its FK reference. The rendered body is preserved on the row.
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        doc=(
            "Optional FK to the originating template. NULL means an ad-hoc send "
            "(body supplied directly). SET NULL on template delete: the rendered "
            "snapshot on this row keeps the historical record intact."
        ),
    )
    channel: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Delivery channel. Valid values live in app.channels.Channel; not DB-CHECKed.",
    )

    recipient_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
        doc="Set when channel='email'. Mutually exclusive with recipient_phone (CHECK constraint).",
    )
    recipient_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Set when channel='sms'. Mutually exclusive with recipient_email (CHECK constraint).",
    )

    subject: Mapped[str | None] = mapped_column(
        String(998),
        nullable=True,
        doc=(
            "Rendered email subject, copied from the template at enqueue time "
            "(or supplied directly for ad-hoc sends). Stored here so the "
            "notification is a self-contained historical record even after the "
            "template is edited or deleted. NULL for SMS sends."
        ),
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc=(
            "Rendered message body. For templated sends, this is the template "
            "body after Jinja2 substitution at enqueue time. For ad-hoc sends, "
            "this is the body supplied by the caller. The notification row is "
            "the audit record of what was actually sent, independent of the "
            "current state of any referenced template."
        ),
    )
    variables: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc=(
            "Raw variables supplied to the template renderer, kept for audit "
            "and debugging. The rendered text alone cannot be reverse-engineered "
            "into the variable map, so this is the only way to answer 'what "
            "exact values produced this output?' after the fact."
        ),
    )

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING,
        doc=(
            "State machine: 'pending' (initial, awaiting worker), "
            "'sent' (terminal), 'failed' (terminal). Validated by CHECK."
        ),
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc=(
            "Set only when status='failed'. Prefixed with 'permanent: ' or "
            "'transient: ' (see app.domains.notification.constants."
            "FAILURE_REASON_*_PREFIX) to categorise the failure for the "
            "tenant's dashboard."
        ),
    )
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Set only when status='sent'. The provider's (SendGrid/Twilio) message ID for support tickets.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Notification id={self.id} tenant={self.tenant_id} "
            f"channel={self.channel!r} status={self.status!r}>"
        )
