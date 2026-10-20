from __future__ import annotations
from uuid import uuid4

from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class RegressionComparison(Base, TimestampMixin):
    __tablename__ = "regression_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    baseline_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    candidate_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    """
    {
      "new_failures": [...], "resolved_failures": [...], "unchanged_failures": [...],
      "newly_passed": [...], "non_comparable": [...], "critical_failures": [...],
      "category_changes": {...}
    }
    """
