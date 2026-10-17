"""mRNA construct simulation tables

Revision ID: 0006_constructs
Revises: 0005_neoantigen
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_constructs"
down_revision: Union[str, None] = "0005_neoantigen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_constructs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, server_default="Simulation Construct"),
        sa.Column("simulation_format", sa.String(length=32), nullable=False, server_default="mRNA-LNP"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("candidate_ids", sa.JSON(), nullable=True),
        sa.Column("ordering", sa.JSON(), nullable=True),
        sa.Column("construct_representation", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Text(), nullable=True),
        sa.Column("selected_by", sa.String(length=128), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candidate_version", sa.String(length=64), nullable=True),
        sa.Column("qc_summary", sa.JSON(), nullable=True),
        sa.Column("validation", sa.JSON(), nullable=True),
        sa.Column("simulation_output", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_simulation_constructs_analysis_run_id"), "simulation_constructs", ["analysis_run_id"])
    op.create_index(op.f("ix_simulation_constructs_status"), "simulation_constructs", ["status"])

    op.create_table(
        "construct_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("construct_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("spacer", sa.String(length=64), nullable=True),
        sa.Column("selected_by", sa.String(length=128), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candidate_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["construct_id"], ["simulation_constructs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_construct_items_construct_id"), "construct_items", ["construct_id"])
    op.create_index(op.f("ix_construct_items_candidate_id"), "construct_items", ["candidate_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_construct_items_candidate_id"), table_name="construct_items")
    op.drop_index(op.f("ix_construct_items_construct_id"), table_name="construct_items")
    op.drop_table("construct_items")

    op.drop_index(op.f("ix_simulation_constructs_status"), table_name="simulation_constructs")
    op.drop_index(op.f("ix_simulation_constructs_analysis_run_id"), table_name="simulation_constructs")
    op.drop_table("simulation_constructs")
