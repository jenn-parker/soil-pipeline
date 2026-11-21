"""Store stable identity subjects for sample access grants.

Revision ID: 20261120_0005
Revises: 20261120_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261120_0005"
down_revision: Union[str, Sequence[str], None] = "20261120_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "soil_sample_access",
        sa.Column("user_sub", sa.String(length=255), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_soil_sample_access_sample_sub "
        "ON soil_sample_access (soil_sample_id, user_sub) "
        "WHERE user_sub IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_soil_sample_access_sample_sub")
    op.drop_column("soil_sample_access", "user_sub")
