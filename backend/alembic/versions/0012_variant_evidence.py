"""add variant evidence records

Revision ID: 0012_variant_evidence
Revises: 0011_hgvs
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_variant_evidence"
down_revision: Union[str, None] = "0011_hgvs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "variant_evidence_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("provider_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("population_frequency", sa.Float(), nullable=True),
        sa.Column("known_driver", sa.Boolean(), nullable=True),
        sa.Column("clinical_significance", sa.Text(), nullable=True),
        sa.Column("identifiers", sa.JSON(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["variant_id"], ["variants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_variant_evidence_records_analysis_run_id"),
        "variant_evidence_records",
        ["analysis_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_variant_evidence_records_variant_id"),
        "variant_evidence_records",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_variant_evidence_records_provider"),
        "variant_evidence_records",
        ["provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_variant_evidence_records_provider"), table_name="variant_evidence_records")
    op.drop_index(op.f("ix_variant_evidence_records_variant_id"), table_name="variant_evidence_records")
    op.drop_index(op.f("ix_variant_evidence_records_analysis_run_id"), table_name="variant_evidence_records")
    op.drop_table("variant_evidence_records")
