"""neoantigen candidate engine tables

Revision ID: 0005_neoantigen
Revises: 0004_hla_expression
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_neoantigen"
down_revision: Union[str, None] = "0004_hla_expression"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ranking_configurations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("weights", sa.JSON(), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ranking_configurations_project_id"),
        "ranking_configurations",
        ["project_id"],
        unique=True,
    )

    op.add_column(
        "analysis_runs",
        sa.Column("ranking_configuration_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "analysis_runs", sa.Column("ranking_config", sa.JSON(), nullable=True)
    )

    op.create_table(
        "neoantigen_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=True),
        sa.Column("somatic_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("hla_profile_id", sa.String(length=36), nullable=True),
        sa.Column("gene", sa.String(length=128), nullable=True),
        sa.Column("gene_id", sa.String(length=128), nullable=True),
        sa.Column("transcript", sa.String(length=128), nullable=True),
        sa.Column("transcript_id", sa.String(length=128), nullable=True),
        sa.Column("protein_change", sa.String(length=128), nullable=True),
        sa.Column("consequence", sa.String(length=32), nullable=True),
        sa.Column("impact", sa.String(length=16), nullable=True),
        sa.Column("peptide_representation", sa.String(length=512), nullable=False),
        sa.Column("peptide_sequence", sa.String(length=128), nullable=True),
        sa.Column("hla_allele", sa.String(length=64), nullable=True),
        sa.Column("hla_class", sa.String(length=4), nullable=True),
        sa.Column("expression_evidence", sa.JSON(), nullable=True),
        sa.Column("mutation_evidence", sa.JSON(), nullable=True),
        sa.Column("prediction_status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="GENERATED"),
        sa.Column("ranking_score", sa.Float(), nullable=True),
        sa.Column("ranking_evidence", sa.JSON(), nullable=True),
        sa.Column("ranking_configuration_id", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["variants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["somatic_candidate_id"], ["somatic_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hla_profile_id"], ["hla_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_neoantigen_candidates_analysis_run_id"), "neoantigen_candidates", ["analysis_run_id"])
    op.create_index(op.f("ix_neoantigen_candidates_hla_allele"), "neoantigen_candidates", ["hla_allele"])
    op.create_index(op.f("ix_neoantigen_candidates_prediction_status"), "neoantigen_candidates", ["prediction_status"])
    op.create_index(op.f("ix_neoantigen_candidates_status"), "neoantigen_candidates", ["status"])
    op.create_index(op.f("ix_neoantigen_candidates_ranking_score"), "neoantigen_candidates", ["ranking_score"])

    op.create_table(
        "prediction_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("hla", sa.String(length=64), nullable=True),
        sa.Column("prediction_value", sa.Float(), nullable=True),
        sa.Column("metric_name", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["neoantigen_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prediction_results_candidate_id"), "prediction_results", ["candidate_id"])
    op.create_index(op.f("ix_prediction_results_analysis_run_id"), "prediction_results", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_prediction_results_analysis_run_id"), table_name="prediction_results")
    op.drop_index(op.f("ix_prediction_results_candidate_id"), table_name="prediction_results")
    op.drop_table("prediction_results")

    op.drop_index(op.f("ix_neoantigen_candidates_ranking_score"), table_name="neoantigen_candidates")
    op.drop_index(op.f("ix_neoantigen_candidates_status"), table_name="neoantigen_candidates")
    op.drop_index(op.f("ix_neoantigen_candidates_prediction_status"), table_name="neoantigen_candidates")
    op.drop_index(op.f("ix_neoantigen_candidates_hla_allele"), table_name="neoantigen_candidates")
    op.drop_index(op.f("ix_neoantigen_candidates_analysis_run_id"), table_name="neoantigen_candidates")
    op.drop_table("neoantigen_candidates")

    op.drop_column("analysis_runs", "ranking_config")
    op.drop_column("analysis_runs", "ranking_configuration_id")

    op.drop_index(op.f("ix_ranking_configurations_project_id"), table_name="ranking_configurations")
    op.drop_table("ranking_configurations")
