"""add expression quantification

Revision ID: 0013_expression_quantification
Revises: 0012_variant_evidence
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_expression_quantification"
down_revision: Union[str, None] = "0012_variant_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "expression_quantifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("gene_id", sa.String(length=64), nullable=True),
        sa.Column("gene_symbol", sa.String(length=64), nullable=True),
        sa.Column("tumor_value", sa.Float(), nullable=True),
        sa.Column("normal_value", sa.Float(), nullable=True),
        sa.Column("log2_fold_change", sa.Float(), nullable=True),
        sa.Column("is_expressed", sa.Boolean(), nullable=False),
        sa.Column("differentially_expressed", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("pseudocount", sa.Float(), nullable=True),
        sa.Column("expression_threshold", sa.Float(), nullable=True),
        sa.Column("log2fc_threshold", sa.Float(), nullable=True),
        sa.Column("samples", sa.JSON(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_expression_quantifications_analysis_run_id"),
        "expression_quantifications",
        ["analysis_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_expression_quantifications_gene_id"),
        "expression_quantifications",
        ["gene_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_expression_quantifications_gene_id"), table_name="expression_quantifications")
    op.drop_index(op.f("ix_expression_quantifications_analysis_run_id"), table_name="expression_quantifications")
    op.drop_table("expression_quantifications")
