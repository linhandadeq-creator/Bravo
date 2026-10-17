"""add project case information

Revision ID: 0016_project_case_info
Revises: 0015_project_notes_reminders
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_project_case_info"
down_revision: Union[str, None] = "0015_project_notes_reminders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("age", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("sex", sa.String(length=16), nullable=True))
    op.add_column("projects", sa.Column("cancer_type", sa.String(length=128), nullable=True))
    op.add_column("projects", sa.Column("stage", sa.String(length=64), nullable=True))
    op.add_column("projects", sa.Column("diagnosis", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "diagnosis")
    op.drop_column("projects", "stage")
    op.drop_column("projects", "cancer_type")
    op.drop_column("projects", "sex")
    op.drop_column("projects", "age")
