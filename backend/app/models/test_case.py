from __future__ import annotations
from uuid import uuid4

from sqlalchemy import String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin
from app.enums import Severity, BehaviorType


class TestCase(Base, TimestampMixin):
    __test__ = False  # not a pytest test class -- this is a TrustTrace domain model
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    evaluation_pack_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluation_packs.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    severity: Mapped[Severity] = mapped_column(String(20), default=Severity.MEDIUM, nullable=False)

    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    """Query text, document references, structured args -- whatever the adapter needs."""

    behavior_type: Mapped[BehaviorType] = mapped_column(
        String(30), default=BehaviorType.FREE_TEXT, nullable=False
    )
    expected_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_evidence: Mapped[list] = mapped_column(JSON, default=list)
    """List of {"document_id": str, "page": int, "passage_id": str (optional)}."""

    relevant_passage_ids: Mapped[list] = mapped_column(JSON, default=list)
    """Passage IDs considered relevant, for retrieval-metric evaluators."""

    expected_tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    prohibited_tool_calls: Mapped[list] = mapped_column(JSON, default=list)

    evaluator_config: Mapped[dict] = mapped_column(JSON, default=dict)
    """Per-evaluator settings for this case, e.g. {"factual_correctness": {"tolerance": 0.01}}."""

    preconditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
