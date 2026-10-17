"""HLA and expression tables

Revision ID: 0004_hla_expression
Revises: 0003_annotation
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_hla_expression"
down_revision: Union[str, None] = "0003_annotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hla_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("allele", sa.String(length=64), nullable=True),
        sa.Column("allele_raw", sa.String(length=128), nullable=True),
        sa.Column("allele_class", sa.String(length=4), nullable=True),
        sa.Column("locus", sa.String(length=16), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("invalid_reason", sa.Text(), nullable=True),
        sa.Column("normalization_method", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hla_profiles_analysis_run_id"), "hla_profiles", ["analysis_run_id"])
    op.create_index(op.f("ix_hla_profiles_allele"), "hla_profiles", ["allele"])
    op.create_index(op.f("ix_hla_profiles_allele_class"), "hla_profiles", ["allele_class"])

    op.create_table(
        "expression_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="GENE"),
        sa.Column("gene_id", sa.String(length=64), nullable=True),
        sa.Column("gene_symbol", sa.String(length=64), nullable=True),
        sa.Column("transcript_id", sa.String(length=64), nullable=True),
        sa.Column("expression_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("raw_gene_id", sa.String(length=128), nullable=True),
        sa.Column("raw_transcript_id", sa.String(length=128), nullable=True),
        sa.Column("gene_id_changed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("transcript_id_changed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("gene_id_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("invalid_reason", sa.Text(), nullable=True),
        sa.Column("normalization_method", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expression_records_analysis_run_id"), "expression_records", ["analysis_run_id"])
    op.create_index(op.f("ix_expression_records_gene_id"), "expression_records", ["gene_id"])
    op.create_index(op.f("ix_expression_records_transcript_id"), "expression_records", ["transcript_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_expression_records_transcript_id"), table_name="expression_records")
    op.drop_index(op.f("ix_expression_records_gene_id"), table_name="expression_records")
    op.drop_index(op.f("ix_expression_records_analysis_run_id"), table_name="expression_records")
    op.drop_table("expression_records")

    op.drop_index(op.f("ix_hla_profiles_allele_class"), table_name="hla_profiles")
    op.drop_index(op.f("ix_hla_profiles_allele"), table_name="hla_profiles")
    op.drop_index(op.f("ix_hla_profiles_analysis_run_id"), table_name="hla_profiles")
    op.drop_table("hla_profiles")
