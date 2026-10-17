import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    sample_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("samples.id", ondelete="SET NULL"), nullable=True
    )
    sample_role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chromosome: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    chromosome_normalized: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chromosome_normalized_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reference: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    alternate: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    filter: Mapped[str | None] = mapped_column(String(256), nullable=True)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allele_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    genotype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    record_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    format_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_malformed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis_run = relationship("AnalysisRun", back_populates="variants")
