"""validation framework tables

Revision ID: 0007_validation
Revises: 0006_constructs
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_validation"
down_revision: Union[str, None] = "0006_constructs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_build", sa.String(length=16), nullable=True),
        sa.Column("expected", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_validation_datasets_name"), "validation_datasets", ["name"], unique=True)

    op.create_table(
        "validation_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=True),
        sa.Column("software_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pipeline_health", sa.JSON(), nullable=True),
        sa.Column("category_summary", sa.JSON(), nullable=True),
        sa.Column("reproducibility", sa.JSON(), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["validation_datasets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_validation_reports_status"), "validation_reports", ["status"])

    op.create_table(
        "validation_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("expected_result", sa.JSON(), nullable=True),
        sa.Column("actual_result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["validation_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_validation_cases_report_id"), "validation_cases", ["report_id"])
    op.create_index(op.f("ix_validation_cases_category"), "validation_cases", ["category"])
    op.create_index(op.f("ix_validation_cases_status"), "validation_cases", ["status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=True),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["validation_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_report_id"), "audit_logs", ["report_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_report_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_validation_cases_status"), table_name="validation_cases")
    op.drop_index(op.f("ix_validation_cases_category"), table_name="validation_cases")
    op.drop_index(op.f("ix_validation_cases_report_id"), table_name="validation_cases")
    op.drop_table("validation_cases")

    op.drop_index(op.f("ix_validation_reports_status"), table_name="validation_reports")
    op.drop_table("validation_reports")

    op.drop_index(op.f("ix_validation_datasets_name"), table_name="validation_datasets")
    op.drop_table("validation_datasets")
