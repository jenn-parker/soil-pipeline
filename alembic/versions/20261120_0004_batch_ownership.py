"""Track the authenticated creator of upload batches.

Revision ID: 20261120_0004
Revises: 20261102_0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261120_0004"
down_revision: Union[str, Sequence[str], None] = "20261102_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "soil_upload_batches",
        sa.Column("created_by_sub", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_soil_upload_batches_created_by_sub",
        "soil_upload_batches",
        ["created_by_sub"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_soil_upload_batches_created_by_sub",
        table_name="soil_upload_batches",
    )
    op.drop_column("soil_upload_batches", "created_by_sub")
