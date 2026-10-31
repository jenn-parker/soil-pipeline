"""Add sample ownership and sharing records.

Revision ID: 20261101_0002
Revises: 20261030_0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_0002"
down_revision: Union[str, Sequence[str], None] = "20261030_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("soil_samples", sa.Column("created_by_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_soil_samples_created_by_sub", "soil_samples", ["created_by_sub"])
    op.create_table(
        "soil_sample_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("soil_sample_id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        sa.Column("granted_by_sub", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["soil_sample_id"], ["soil_samples.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("soil_sample_id", "user_email", name="uq_soil_sample_access_sample_email"),
    )
    op.create_index("ix_soil_sample_access_soil_sample_id", "soil_sample_access", ["soil_sample_id"])
    op.create_index("ix_soil_sample_access_user_email", "soil_sample_access", ["user_email"])


def downgrade() -> None:
    op.drop_table("soil_sample_access")
    op.drop_index("ix_soil_samples_created_by_sub", table_name="soil_samples")
    op.drop_column("soil_samples", "created_by_sub")
