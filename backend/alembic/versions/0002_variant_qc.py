"""variant input and QC tables

Revision ID: 0002_variant_qc
Revises: 0001_create_projects
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_variant_qc"
down_revision: Union[str, None] = "0001_create_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "samples",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sample_type", sa.String(length=16), nullable=False),
        sa.Column("reference_build", sa.String(length=16), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="UPLOAD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_samples_project_id"), "samples", ["project_id"])
    op.create_index(op.f("ix_samples_sample_type"), "samples", ["sample_type"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("tumor_sample_id", sa.String(length=36), nullable=True),
        sa.Column("normal_sample_id", sa.String(length=36), nullable=True),
        sa.Column("reference_build", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="UPLOAD"),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("qc_summary", sa.JSON(), nullable=True),
        sa.Column("somatic_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tumor_sample_id"], ["samples.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["normal_sample_id"], ["samples.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_runs_project_id"), "analysis_runs", ["project_id"])
    op.create_index(op.f("ix_analysis_runs_status"), "analysis_runs", ["status"])

    op.create_table(
        "variants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("sample_id", sa.String(length=36), nullable=True),
        sa.Column("sample_role", sa.String(length=16), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("chromosome", sa.String(length=64), nullable=True),
        sa.Column("chromosome_normalized", sa.String(length=64), nullable=True),
        sa.Column("chromosome_normalized_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("reference", sa.String(length=1024), nullable=True),
        sa.Column("alternate", sa.String(length=1024), nullable=True),
        sa.Column("quality", sa.Float(), nullable=True),
        sa.Column("filter", sa.String(length=256), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=True),
        sa.Column("allele_frequency", sa.Float(), nullable=True),
        sa.Column("genotype", sa.String(length=64), nullable=True),
        sa.Column("variant_type", sa.String(length=32), nullable=True),
        sa.Column("record_id", sa.String(length=256), nullable=True),
        sa.Column("info", sa.JSON(), nullable=True),
        sa.Column("format_fields", sa.JSON(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_malformed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("invalid_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sample_id"], ["samples.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_variants_analysis_run_id"), "variants", ["analysis_run_id"])
    op.create_index(op.f("ix_variants_sample_role"), "variants", ["sample_role"])
    op.create_index(op.f("ix_variants_chromosome"), "variants", ["chromosome"])
    op.create_index(op.f("ix_variants_position"), "variants", ["position"])

    op.create_table(
        "somatic_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("chromosome", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=1024), nullable=False),
        sa.Column("alternate", sa.String(length=1024), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("tumor_allele_frequency", sa.Float(), nullable=True),
        sa.Column("normal_allele_frequency", sa.Float(), nullable=True),
        sa.Column("tumor_depth", sa.Integer(), nullable=True),
        sa.Column("normal_depth", sa.Integer(), nullable=True),
        sa.Column("tumor_genotype", sa.String(length=64), nullable=True),
        sa.Column("normal_genotype", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_somatic_candidates_analysis_run_id"),
        "somatic_candidates",
        ["analysis_run_id"],
    )
    op.create_index(
        op.f("ix_somatic_candidates_classification"),
        "somatic_candidates",
        ["classification"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_somatic_candidates_classification"), table_name="somatic_candidates")
    op.drop_index(op.f("ix_somatic_candidates_analysis_run_id"), table_name="somatic_candidates")
    op.drop_table("somatic_candidates")

    op.drop_index(op.f("ix_variants_position"), table_name="variants")
    op.drop_index(op.f("ix_variants_chromosome"), table_name="variants")
    op.drop_index(op.f("ix_variants_sample_role"), table_name="variants")
    op.drop_index(op.f("ix_variants_analysis_run_id"), table_name="variants")
    op.drop_table("variants")

    op.drop_index(op.f("ix_analysis_runs_status"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_project_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")

    op.drop_index(op.f("ix_samples_sample_type"), table_name="samples")
    op.drop_index(op.f("ix_samples_project_id"), table_name="samples")
    op.drop_table("samples")
