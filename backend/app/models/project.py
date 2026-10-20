from __future__ import annotations
from uuid import uuid4

from sqlalchemy import String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.enums import IntegrationType, IntegrationStatus


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_pack_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("evaluation_packs.id"), nullable=True
    )

    integrations: Mapped[list["Integration"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    evaluation_pack = relationship("EvaluationPack")


class Integration(Base, TimestampMixin):
    """
    An integration is TrustTrace's configured connection to one target
    application via one adapter type. Secrets referenced in `config` are
    stored as opaque references (e.g. "secret:some-key"), never plaintext
    values -- see app/secrets.py for resolution.
    """

    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_type: Mapped[IntegrationType] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[IntegrationStatus] = mapped_column(
        String(20), default=IntegrationStatus.NOT_TESTED, nullable=False
    )
    last_validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="integrations")
