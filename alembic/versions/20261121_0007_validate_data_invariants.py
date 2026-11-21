"""Validate existing data and add provenance/measurement invariants.

Revision ID: 20261121_0007
Revises: 20261121_0006
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261121_0007"
down_revision: Union[str, Sequence[str], None] = "20261121_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CONSTRAINTS = (
    (
        "soil_upload_batches",
        "ck_soil_upload_batches_final_row_counts",
        "status = 'processing' OR accepted_rows + rejected_rows = total_rows",
    ),
    ("soil_samples", "ck_soil_samples_sampling_depth_nonnegative", "sampling_depth_inches IS NULL OR sampling_depth_inches >= 0"),
    ("soil_samples", "ck_soil_samples_bulk_density_nonnegative", "bulk_density_g_cm3 IS NULL OR bulk_density_g_cm3 >= 0"),
    ("soil_samples", "ck_soil_samples_nitrate_nonnegative", "nitrate_nitrogen_ppm IS NULL OR nitrate_nitrogen_ppm >= 0"),
    ("soil_samples", "ck_soil_samples_phosphorus_nonnegative", "phosphorus_ppm IS NULL OR phosphorus_ppm >= 0"),
    ("soil_samples", "ck_soil_samples_potassium_nonnegative", "potassium_ppm IS NULL OR potassium_ppm >= 0"),
    ("soil_samples", "ck_soil_samples_sulfur_nonnegative", "sulfur_ppm IS NULL OR sulfur_ppm >= 0"),
    ("sample_identifications", "ck_sample_identifications_latitude_range", "latitude IS NULL OR latitude BETWEEN -90 AND 90"),
    ("sample_identifications", "ck_sample_identifications_longitude_range", "longitude IS NULL OR longitude BETWEEN -180 AND 180"),
    ("sample_identifications", "ck_sample_identifications_coordinate_pair", "(latitude IS NULL) = (longitude IS NULL)"),
    ("sample_identifications", "ck_sample_identifications_elevation_range", "elevation_meters IS NULL OR elevation_meters BETWEEN -400 AND 9000"),
    ("sample_identifications", "ck_sample_identifications_gps_accuracy_nonnegative", "gps_accuracy_meters IS NULL OR gps_accuracy_meters >= 0"),
    ("sample_identifications", "ck_sample_identifications_sampling_depth_nonnegative", "sampling_depth_cm IS NULL OR sampling_depth_cm >= 0"),
    ("sample_identifications", "ck_sample_identifications_cores_positive", "cores_per_composite IS NULL OR cores_per_composite >= 1"),
)

EXISTING_CONSTRAINTS = (
    "ck_soil_upload_batches_status",
    "ck_soil_upload_batches_archive_status",
    "ck_soil_upload_batches_row_counts",
    "ck_soil_samples_latitude_range",
    "ck_soil_samples_longitude_range",
    "ck_soil_samples_coordinate_pair",
    "ck_soil_samples_soil_ph_range",
    "ck_soil_samples_buffer_ph_range",
    "ck_soil_samples_sand_pct_range",
    "ck_soil_samples_silt_pct_range",
    "ck_soil_samples_clay_pct_range",
    "ck_soil_samples_calcium_saturation_range",
    "ck_soil_samples_magnesium_saturation_range",
    "ck_soil_samples_potassium_saturation_range",
    "ck_soil_samples_hydrogen_saturation_range",
    "ck_soil_samples_sodium_saturation_range",
)


def upgrade() -> None:
    for table, name, expression in NEW_CONSTRAINTS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression}) NOT VALID"
        )

    for table, name, _ in NEW_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")

    table_by_constraint = {
        **{name: "soil_upload_batches" for name in EXISTING_CONSTRAINTS[:3]},
        **{name: "soil_samples" for name in EXISTING_CONSTRAINTS[3:]},
    }
    for name in EXISTING_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table_by_constraint[name]} VALIDATE CONSTRAINT {name}")


def downgrade() -> None:
    for table, name, _ in reversed(NEW_CONSTRAINTS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
