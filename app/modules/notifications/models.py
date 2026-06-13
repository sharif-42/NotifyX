from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums import (
    NotificationAttemptStatus,
    NotificationStatus,
    NotificationType,
    RetryJobStatus,
)

if TYPE_CHECKING:
    from app.modules.templates.models import Template
    from app.modules.tenants.models import Tenant


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_tenant_created_at_desc", "tenant_id", "created_at"),
        Index("ix_notifications_status_created_at_desc", "status", "created_at"),
        Index("ix_notifications_type_created_at_desc", "type", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=False),
        nullable=False,
    )
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status", native_enum=False),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="notifications")
    template: Mapped["Template | None"] = relationship(back_populates="notifications")
    attempts: Mapped[list["NotificationAttempt"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
    )


class NotificationAttempt(Base):
    __tablename__ = "notification_attempts"
    __table_args__ = (
        Index(
            "uq_notification_attempts_notification_id_attempt_number",
            "notification_id",
            "attempt_number",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    notification_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[NotificationAttemptStatus] = mapped_column(
        Enum(
            NotificationAttemptStatus,
            name="notification_attempt_status",
            native_enum=False,
        ),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    notification: Mapped["Notification"] = relationship(back_populates="attempts")


class Outbox(Base):
    """Outbox row for the at-least-once publish pattern.

    Created in the same transaction as the corresponding ``Notification``.
    The outbox worker polls unpublished rows, publishes the rendered payload
    to the per-channel RabbitMQ queue, and sets ``published_at`` once the
    broker ACKs. The API never touches RabbitMQ — it only writes to this
    table.
    """

    __tablename__ = "outbox"
    __table_args__ = (
        # Poller query: WHERE published_at IS NULL ORDER BY created_at LIMIT K
        Index("ix_outbox_published_at_created_at", "published_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    notification_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="outbox_channel", native_enum=False),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notification: Mapped["Notification"] = relationship()


class RetryJob(Base):
    """DB-driven retry queue for transient provider failures.

    Populated by the channel dispatcher on transient failure. The retry
    worker claims rows with ``SELECT ... FOR UPDATE SKIP LOCKED`` and
    re-dispatches into the channel dispatcher. On exhaustion the row is
    deleted and the notification is moved to ``FAILED``.
    """

    __tablename__ = "retry_jobs"
    __table_args__ = (
        # Poller query: WHERE status = 'PENDING' AND next_retry_at <= now()
        # ORDER BY next_retry_at LIMIT K FOR UPDATE SKIP LOCKED
        Index("ix_retry_jobs_next_retry_at_status", "next_retry_at", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    notification_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[RetryJobStatus] = mapped_column(
        Enum(RetryJobStatus, name="retry_job_status", native_enum=False),
        nullable=False,
        default=RetryJobStatus.PENDING,
        server_default=RetryJobStatus.PENDING.value,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
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

    notification: Mapped["Notification"] = relationship()
