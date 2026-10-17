import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

CASE_PASS = "PASS"
CASE_FAIL = "FAIL"
CASE_WARNING = "WARNING"

REPORT_VALIDATED = "VALIDATED_SOFTWARE_BUILD"
REPORT_NOT_VALIDATED = "NOT_VALIDATED"


class ValidationDataset(Base):
    __tablename__ = "validation_datasets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_build: Mapped[str | None] = mapped_column(String(16), nullable=True)
    expected: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dataset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("validation_datasets.id", ondelete="SET NULL"), nullable=True
    )
    software_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pipeline_health: Mapped[list | None] = mapped_column(JSON, nullable=True)
    category_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reproducibility: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cases = relationship(
        "ValidationCase",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ValidationCase(Base):
    __tablename__ = "validation_cases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("validation_reports.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actual_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report = relationship("ValidationReport", back_populates="cases")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("validation_reports.id", ondelete="CASCADE"), nullable=True, index=True
    )
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report = relationship("ValidationReport", back_populates="audit_logs")
