import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

MODE_UPLOAD = "UPLOAD"
MODE_SYNTHETIC = "SYNTHETIC"


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    tumor_sample_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("samples.id", ondelete="SET NULL"), nullable=True
    )
    normal_sample_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("samples.id", ondelete="SET NULL"), nullable=True
    )
    reference_build: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default=MODE_UPLOAD)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    qc_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    somatic_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ranking_configuration_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    ranking_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project = relationship("Project", backref="analysis_runs")
    tumor_sample = relationship("Sample", foreign_keys=[tumor_sample_id])
    normal_sample = relationship("Sample", foreign_keys=[normal_sample_id])
    variants = relationship(
        "Variant",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    evidence_records = relationship(
        "VariantEvidenceRecord",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    candidates = relationship(
        "SomaticCandidate",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
