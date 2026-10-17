"""add project files and patient name

Revision ID: 0014_project_files
Revises: 0013_expression_quantification
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_project_files"
down_revision: Union[str, None] = "0013_expression_quantification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("patient_name", sa.String(length=255), nullable=True))
    op.create_table(
        "project_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_files_project_id"),
        "project_files",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_files_kind"),
        "project_files",
        ["kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_files_kind"), table_name="project_files")
    op.drop_index(op.f("ix_project_files_project_id"), table_name="project_files")
    op.drop_table("project_files")
    op.drop_column("projects", "patient_name")
