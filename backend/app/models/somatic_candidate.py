import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SomaticCandidate(Base):
    __tablename__ = "somatic_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    chromosome: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    alternate: Mapped[str] = mapped_column(String(1024), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    tumor_allele_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    normal_allele_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    tumor_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normal_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tumor_genotype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normal_genotype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis_run = relationship("AnalysisRun", back_populates="candidates")
