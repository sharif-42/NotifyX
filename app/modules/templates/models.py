from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums import TemplateChannel

if TYPE_CHECKING:
    from app.modules.notifications.models import Notification
    from app.modules.tenants.models import Tenant


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        Index("uq_templates_tenant_name_channel", "tenant_id", "name", "channel", unique=True),
        Index("ix_templates_tenant_created_at_desc", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[TemplateChannel] = mapped_column(
        Enum(TemplateChannel, name="template_channel", native_enum=False),
        nullable=False,
        default=TemplateChannel.EMAIL,
        server_default=TemplateChannel.EMAIL.value,
    )
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    tenant: Mapped["Tenant"] = relationship(back_populates="templates")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="template")
