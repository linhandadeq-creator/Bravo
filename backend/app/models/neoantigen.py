import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

CANDIDATE_GENERATED = "GENERATED"
CANDIDATE_PREDICTED = "PREDICTED"
CANDIDATE_RANKED = "RANKED"
CANDIDATE_REJECTED = "REJECTED"
CANDIDATE_UNCERTAIN = "UNCERTAIN"
CANDIDATE_FAILED = "FAILED"

PREDICTION_PENDING = "PENDING"
PREDICTION_MOCK = "MOCK"
PREDICTION_AVAILABLE = "AVAILABLE"
PREDICTION_UNAVAILABLE = "UNAVAILABLE"
PREDICTION_FAILED = "FAILED"


class RankingConfiguration(Base):
    __tablename__ = "ranking_configurations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NeoantigenCandidate(Base):
    __tablename__ = "neoantigen_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="SET NULL"), nullable=True
    )
    somatic_candidate_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("somatic_candidates.id", ondelete="SET NULL"), nullable=True
    )
    hla_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("hla_profiles.id", ondelete="SET NULL"), nullable=True
    )

    gene: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gene_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transcript: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transcript_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protein_change: Mapped[str | None] = mapped_column(String(128), nullable=True)
    consequence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(16), nullable=True)

    peptide_representation: Mapped[str] = mapped_column(String(512), nullable=False)
    peptide_sequence: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hla_allele: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hla_class: Mapped[str | None] = mapped_column(String(4), nullable=True)

    expression_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mutation_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    prediction_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PREDICTION_PENDING, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CANDIDATE_GENERATED, index=True
    )
    ranking_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    ranking_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ranking_configuration_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    analysis_run = relationship("AnalysisRun", backref="neoantigen_candidates")
    predictions = relationship(
        "PredictionResult",
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("neoantigen_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    hla: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prediction_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate = relationship("NeoantigenCandidate", back_populates="predictions")
