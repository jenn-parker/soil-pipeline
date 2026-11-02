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
    # IF NOT EXISTS keeps this revision safe for databases where an earlier
    # pre-release archive migration already added one or both columns.
    op.execute(
        "ALTER TABLE soil_upload_batches "
        "ADD COLUMN IF NOT EXISTS archive_fenced_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE soil_upload_batches "
        "ADD COLUMN IF NOT EXISTS archive_fence_reason VARCHAR(100)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE soil_upload_batches DROP COLUMN IF EXISTS archive_fence_reason")
    op.execute("ALTER TABLE soil_upload_batches DROP COLUMN IF EXISTS archive_fenced_at")
