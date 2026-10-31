"""Create the current application schema.

Revision ID: 20261030_0001
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision: str = "20261030_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "soil_upload_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_bucket", sa.String(length=255), nullable=True),
        sa.Column("source_key", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="processing"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "soil_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("sample_id", sa.String(length=50), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sampling_depth_inches", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("soil_ph", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("buffer_ph", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("organic_matter_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("cation_exchange_capacity", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("electrical_conductivity", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("nitrate_nitrogen_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("phosphorus_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("phosphorus_extraction_method", sa.String(length=50), nullable=True),
        sa.Column("potassium_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("sulfur_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("calcium_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("magnesium_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("sodium_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("zinc_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("iron_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("manganese_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("copper_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("boron_ppm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("sand_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("silt_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("clay_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("bulk_density_g_cm3", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("calcium_saturation_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("magnesium_saturation_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("potassium_saturation_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("hydrogen_saturation_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("sodium_saturation_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["soil_upload_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sample_identifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("soil_sample_id", sa.Integer(), nullable=True),
        sa.Column("sample_id", sa.String(length=100), nullable=False),
        sa.Column("alternate_id", sa.String(length=100), nullable=True),
        sa.Column("collection_date", sa.Date(), nullable=False),
        sa.Column("collection_time", sa.DateTime(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("collector_id", sa.Integer(), nullable=True),
        sa.Column("farm_name", sa.String(length=255), nullable=True),
        sa.Column("field_name", sa.String(length=255), nullable=True),
        sa.Column("management_zone", sa.String(length=100), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state_province", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True, server_default="USA"),
        sa.Column("legal_description", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("elevation_meters", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("gps_accuracy_meters", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("sampling_depth_cm", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("cores_per_composite", sa.Integer(), nullable=True),
        sa.Column("sampling_method", sa.String(length=100), nullable=True),
        sa.Column("previous_crop", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["collector_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["soil_sample_id"], ["soil_samples.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_parties_name", "parties", ["name"])
    op.create_index("ix_soil_samples_batch_id", "soil_samples", ["batch_id"])
    op.create_index("ix_soil_samples_sample_id", "soil_samples", ["sample_id"], unique=True)
    op.create_index("idx_soil_samples_location", "soil_samples", ["location"], postgresql_using="gist")
    op.create_index("ix_sample_identifications_soil_sample_id", "sample_identifications", ["soil_sample_id"], unique=True)
    op.create_index("ix_sample_identifications_sample_id", "sample_identifications", ["sample_id"], unique=True)
    op.create_index("ix_sample_identifications_collection_date", "sample_identifications", ["collection_date"])
    op.create_index("ix_sample_identifications_farm_name", "sample_identifications", ["farm_name"])
    op.create_index("ix_sample_identifications_field_name", "sample_identifications", ["field_name"])


def downgrade() -> None:
    op.drop_table("sample_identifications")
    op.drop_table("soil_samples")
    op.drop_table("soil_upload_batches")
    op.drop_table("parties")
