import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

CONSTRUCT_DRAFT = "DRAFT"
CONSTRUCT_VALIDATED = "VALIDATED_SIMULATION"
CONSTRUCT_INVALID = "INVALID"
CONSTRUCT_LOCKED = "LOCKED"

DEFAULT_SIMULATION_FORMAT = "mRNA-LNP"


class SimulationConstruct(Base):
    """A research-simulation mRNA construct.

    This is a computational research artifact. All generated manufacturing,
    dosing and clinical content is a simulation and is not for clinical use.
    """

    __tablename__ = "simulation_constructs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Simulation Construct")
    simulation_format: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DEFAULT_SIMULATION_FORMAT
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=CONSTRUCT_DRAFT, index=True)

    candidate_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ordering: Mapped[list | None] = mapped_column(JSON, nullable=True)
    construct_representation: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[str | None] = mapped_column(Text, nullable=True)

    selected_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candidate_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    qc_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    simulation_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    analysis_run = relationship("AnalysisRun", backref="simulation_constructs")
    items = relationship(
        "ConstructItem",
        back_populates="construct",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConstructItem.position",
    )


class ConstructItem(Base):
    __tablename__ = "construct_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    construct_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_constructs.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    spacer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candidate_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    construct = relationship("SimulationConstruct", back_populates="items")
