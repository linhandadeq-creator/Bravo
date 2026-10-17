"""add known-variant evidence to variant_annotations

Revision ID: 0010_known_variants
Revises: 0009_annotation_peptide
Create Date: 2026-10-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_known_variants"
down_revision: Union[str, None] = "0009_annotation_peptide"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "variant_annotations",
        sa.Column("known_variants", sa.JSON(), nullable=True),
    )
    op.add_column(
        "variant_annotations",
        sa.Column("clinical_significance", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("variant_annotations", "clinical_significance")
    op.drop_column("variant_annotations", "known_variants")
