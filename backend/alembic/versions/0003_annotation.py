"""variant annotation tables

Revision ID: 0003_annotation
Revises: 0002_variant_qc
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_annotation"
down_revision: Union[str, None] = "0002_variant_qc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "annotation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("reference_build", sa.String(length=16), nullable=True),
        sa.Column("annotation_version", sa.String(length=64), nullable=True),
        sa.Column("transcript_source", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("variant_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("annotated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("compatibility", sa.JSON(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_annotation_runs_analysis_run_id"), "annotation_runs", ["analysis_run_id"])
    op.create_index(op.f("ix_annotation_runs_status"), "annotation_runs", ["status"])

    op.create_table(
        "variant_annotations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("annotation_run_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=True),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("consequence", sa.String(length=32), nullable=True),
        sa.Column("impact", sa.String(length=16), nullable=True),
        sa.Column("gene", sa.String(length=128), nullable=True),
        sa.Column("gene_id", sa.String(length=128), nullable=True),
        sa.Column("transcript", sa.String(length=128), nullable=True),
        sa.Column("transcript_id", sa.String(length=128), nullable=True),
        sa.Column("protein_change", sa.String(length=128), nullable=True),
        sa.Column("cds_position", sa.Integer(), nullable=True),
        sa.Column("protein_position", sa.Integer(), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("reference_build", sa.String(length=16), nullable=True),
        sa.Column("annotation_version", sa.String(length=64), nullable=True),
        sa.Column("transcript_source", sa.String(length=128), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("annotation_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["annotation_run_id"], ["annotation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_variant_annotations_annotation_run_id"), "variant_annotations", ["annotation_run_id"])
    op.create_index(op.f("ix_variant_annotations_variant_id"), "variant_annotations", ["variant_id"])
    op.create_index(op.f("ix_variant_annotations_analysis_run_id"), "variant_annotations", ["analysis_run_id"])
    op.create_index(op.f("ix_variant_annotations_status"), "variant_annotations", ["status"])
    op.create_index(op.f("ix_variant_annotations_consequence"), "variant_annotations", ["consequence"])

    op.create_table(
        "annotation_filter_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("allowed_consequences", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_annotation_filter_configs_project_id"),
        "annotation_filter_configs",
        ["project_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_annotation_filter_configs_project_id"), table_name="annotation_filter_configs")
    op.drop_table("annotation_filter_configs")

    op.drop_index(op.f("ix_variant_annotations_consequence"), table_name="variant_annotations")
    op.drop_index(op.f("ix_variant_annotations_status"), table_name="variant_annotations")
    op.drop_index(op.f("ix_variant_annotations_analysis_run_id"), table_name="variant_annotations")
    op.drop_index(op.f("ix_variant_annotations_variant_id"), table_name="variant_annotations")
    op.drop_index(op.f("ix_variant_annotations_annotation_run_id"), table_name="variant_annotations")
    op.drop_table("variant_annotations")

    op.drop_index(op.f("ix_annotation_runs_status"), table_name="annotation_runs")
    op.drop_index(op.f("ix_annotation_runs_analysis_run_id"), table_name="annotation_runs")
    op.drop_table("annotation_runs")
