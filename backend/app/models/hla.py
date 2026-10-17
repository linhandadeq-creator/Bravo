import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

HLA_CLASS_I = "I"
HLA_CLASS_II = "II"


class HLAProfile(Base):
    __tablename__ = "hla_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    allele: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    allele_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    allele_class: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    locus: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Validation
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance
    normalization_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    analysis_run = relationship("AnalysisRun", backref="hla_profiles")
