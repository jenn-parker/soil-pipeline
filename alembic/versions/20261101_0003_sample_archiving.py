"""Add reversible sample archiving.

Revision ID: 20261101_0003
Revises: 20261101_0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_0003"
down_revision: Union[str, Sequence[str], None] = "20261101_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("soil_samples", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("soil_samples", sa.Column("archived_by_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_soil_samples_archived_at", "soil_samples", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_soil_samples_archived_at", table_name="soil_samples")
    op.drop_column("soil_samples", "archived_by_sub")
    op.drop_column("soil_samples", "archived_at")
