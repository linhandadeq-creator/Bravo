import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AnnotationRun(Base):
    __tablename__ = "annotation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_build: Mapped[str | None] = mapped_column(String(16), nullable=True)
    annotation_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    variant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    annotated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    compatibility: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis_run = relationship("AnalysisRun", backref="annotation_runs")
    annotations = relationship(
        "VariantAnnotation",
        back_populates="annotation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class VariantAnnotation(Base):
    __tablename__ = "variant_annotations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    annotation_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("annotation_runs.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    consequence: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    impact: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gene: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gene_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transcript: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transcript_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protein_change: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cds_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mutated_peptide: Mapped[str | None] = mapped_column(String(64), nullable=True)
    known_variants: Mapped[list | None] = mapped_column(JSON, nullable=True)
    clinical_significance: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hgvs_c: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hgvs_p: Mapped[str | None] = mapped_column(String(256), nullable=True)
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_build: Mapped[str | None] = mapped_column(String(16), nullable=True)
    annotation_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    annotation_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    annotation_run = relationship("AnnotationRun", back_populates="annotations")
    variant = relationship("Variant")
