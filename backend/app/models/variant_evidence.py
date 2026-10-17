import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VariantEvidenceRecord(Base):
    """Population / known-driver / clinical-significance evidence for a variant.

    Every record carries full provenance (provider, version, source, status).
    A lookup that failed is recorded as FAILED — evidence is never silently
    fabricated or replaced by mock data.
    """

    __tablename__ = "variant_evidence_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="CASCADE"), index=True
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="AVAILABLE")
    population_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    known_driver: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    clinical_significance: Mapped[str | None] = mapped_column(Text, nullable=True)
    identifiers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis_run = relationship("AnalysisRun", back_populates="evidence_records")
    variant = relationship("Variant", backref="evidence_records")
