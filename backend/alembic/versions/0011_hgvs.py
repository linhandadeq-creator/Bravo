"""add HGVS c./p. strings to variant_annotations

Revision ID: 0011_hgvs
Revises: 0010_known_variants
Create Date: 2026-10-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_hgvs"
down_revision: Union[str, None] = "0010_known_variants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "variant_annotations",
        sa.Column("hgvs_c", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "variant_annotations",
        sa.Column("hgvs_p", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("variant_annotations", "hgvs_p")
    op.drop_column("variant_annotations", "hgvs_c")
