"""Add durable batch archive state and upload leases.

Revision ID: 20261102_0002
Revises: 20261101_0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_0002"
down_revision: Union[str, Sequence[str], None] = "20261101_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "soil_upload_batches",
        sa.Column("archive_status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    op.add_column("soil_upload_batches", sa.Column("archive_generation", sa.String(length=64), nullable=True))
    op.add_column(
        "soil_upload_batches",
        sa.Column("archive_lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE soil_upload_batches
        SET archive_status = CASE
            WHEN source_key IS NOT NULL THEN 'archived'
            ELSE 'failed'
        END
        """
    )
    op.create_index(
        "ix_soil_upload_batches_archive_status_lease",
        "soil_upload_batches",
        ["archive_status", "archive_lease_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_soil_upload_batches_archive_status_lease", table_name="soil_upload_batches")
    op.drop_column("soil_upload_batches", "archive_lease_until")
    op.drop_column("soil_upload_batches", "archive_generation")
    op.drop_column("soil_upload_batches", "archive_status")
