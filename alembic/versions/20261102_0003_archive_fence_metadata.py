"""Add archive fencing audit metadata.

Revision ID: 20261102_0003
Revises: 20261102_0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_0003"
down_revision: Union[str, Sequence[str], None] = "20261102_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "soil_upload_batches",
        sa.Column("archive_fenced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "soil_upload_batches",
        sa.Column("archive_fence_reason", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("soil_upload_batches", "archive_fence_reason")
    op.drop_column("soil_upload_batches", "archive_fenced_at")
