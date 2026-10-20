from __future__ import annotations
from uuid import uuid4

from sqlalchemy import String, Text, JSON, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class Dataset(Base, TimestampMixin):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    evaluation_pack_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluation_packs.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    versions: Mapped[list["DatasetVersion"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetVersion(Base, TimestampMixin):
    """
    An immutable snapshot of which test case IDs (and their content hash)
    belonged to a dataset at a point in time, so runs stay reproducible
    even if test cases are edited later.
    """

    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    test_case_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    """List of {"test_case_id": str, "content_hash": str} at snapshot time."""

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
