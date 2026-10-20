from __future__ import annotations
from uuid import uuid4

from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class EvaluationPack(Base, TimestampMixin):
    """
    An evaluation pack is Layer C: domain-specific config (business rules,
    field schemas, severities) for testing one kind of target application.
    The generic core only ever reads `rules_config`; it never branches on
    `slug` by name.
    """

    __tablename__ = "evaluation_packs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    rules_config: Mapped[dict] = mapped_column(JSON, default=dict)
