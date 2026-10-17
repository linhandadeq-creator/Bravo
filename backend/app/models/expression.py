import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

LEVEL_GENE = "GENE"
LEVEL_TRANSCRIPT = "TRANSCRIPT"


class ExpressionRecord(Base):
    __tablename__ = "expression_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default=LEVEL_GENE)
    gene_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    gene_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expression_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Normalization audit
    raw_gene_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_transcript_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gene_id_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    transcript_id_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gene_id_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Validation
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance
    normalization_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    analysis_run = relationship("AnalysisRun", backref="expression_records")


class ExpressionQuantification(Base):
    """Tumor-vs-normal RNA-seq quantification for a gene (matrix-level v1).

    Derived from a genes × samples matrix; stores group means, log2 fold
    change and expression calls with full provenance. Not produced by read
    alignment — see docs/rnaseq.md.
    """

    __tablename__ = "expression_quantifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    gene_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    gene_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tumor_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    normal_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    log2_fold_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_expressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    differentially_expressed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    method: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pseudocount: Mapped[float | None] = mapped_column(Float, nullable=True)
    expression_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    log2fc_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    samples: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis_run = relationship("AnalysisRun", backref="expression_quantifications")
