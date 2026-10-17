"""report generation table

Revision ID: 0008_reports
Revises: 0007_validation
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_reports"
down_revision: Union[str, None] = "0007_validation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="GENERATED"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("software_version", sa.String(length=32), nullable=False),
        sa.Column("generated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_analysis_run_id"), "reports", ["analysis_run_id"])
    op.create_index(op.f("ix_reports_project_id"), "reports", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_project_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_analysis_run_id"), table_name="reports")
    op.drop_table("reports")
