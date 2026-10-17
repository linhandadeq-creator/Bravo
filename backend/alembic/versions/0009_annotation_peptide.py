"""add mutated_peptide to variant_annotations

Revision ID: 0009_annotation_peptide
Revises: 0008_reports
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_annotation_peptide"
down_revision: Union[str, None] = "0008_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "variant_annotations",
        sa.Column("mutated_peptide", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("variant_annotations", "mutated_peptide")
