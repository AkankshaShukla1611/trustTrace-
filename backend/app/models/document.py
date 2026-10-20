from __future__ import annotations
from uuid import uuid4

from sqlalchemy import String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


from app.database import Base, TimestampMixin


class DocumentFixture(Base, TimestampMixin):
    """
    A test fixture document (synthetic loan agreement, financial statement,
    etc). `pages` preserves page-level text so evidence citations can
    reference a specific page.
    """

    __tablename__ = "document_fixtures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    """pdf_native | text | json | synthetic"""

    pages: Mapped[list] = mapped_column(JSON, default=list)
    """List of {"page_number": int, "text": str, "sections": list, "tables": list}."""

    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_status: Mapped[str] = mapped_column(String(20), default="ok", nullable=False)
    """ok | partial | failed -- never silently treat unreadable content as extracted."""

    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
