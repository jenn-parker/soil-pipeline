"""Add database checks for application data invariants.

Revision ID: 20261121_0006
Revises: 20261120_0005
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261121_0006"
down_revision: Union[str, Sequence[str], None] = "20261120_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINTS = (
    (
        "soil_upload_batches",
        "ck_soil_upload_batches_status",
        "status IN ('processing', 'completed', 'rejected', 'failed')",
    ),
    (
        "soil_upload_batches",
        "ck_soil_upload_batches_archive_status",
        "archive_status IN ('pending', 'archived', 'failed', 'abandoned')",
    ),
    (
        "soil_upload_batches",
        "ck_soil_upload_batches_row_counts",
        "total_rows >= 0 AND accepted_rows >= 0 AND rejected_rows >= 0 "
        "AND accepted_rows + rejected_rows <= total_rows",
    ),
    ("soil_samples", "ck_soil_samples_latitude_range", "latitude IS NULL OR latitude BETWEEN -90 AND 90"),
    ("soil_samples", "ck_soil_samples_longitude_range", "longitude IS NULL OR longitude BETWEEN -180 AND 180"),
    ("soil_samples", "ck_soil_samples_coordinate_pair", "(latitude IS NULL) = (longitude IS NULL)"),
    ("soil_samples", "ck_soil_samples_soil_ph_range", "soil_ph IS NULL OR soil_ph BETWEEN 0 AND 14"),
    ("soil_samples", "ck_soil_samples_buffer_ph_range", "buffer_ph IS NULL OR buffer_ph BETWEEN 0 AND 14"),
    ("soil_samples", "ck_soil_samples_sand_pct_range", "sand_pct IS NULL OR sand_pct BETWEEN 0 AND 100"),
    ("soil_samples", "ck_soil_samples_silt_pct_range", "silt_pct IS NULL OR silt_pct BETWEEN 0 AND 100"),
    ("soil_samples", "ck_soil_samples_clay_pct_range", "clay_pct IS NULL OR clay_pct BETWEEN 0 AND 100"),
    (
        "soil_samples",
        "ck_soil_samples_calcium_saturation_range",
        "calcium_saturation_pct IS NULL OR calcium_saturation_pct BETWEEN 0 AND 100",
    ),
    (
        "soil_samples",
        "ck_soil_samples_magnesium_saturation_range",
        "magnesium_saturation_pct IS NULL OR magnesium_saturation_pct BETWEEN 0 AND 100",
    ),
    (
        "soil_samples",
        "ck_soil_samples_potassium_saturation_range",
        "potassium_saturation_pct IS NULL OR potassium_saturation_pct BETWEEN 0 AND 100",
    ),
    (
        "soil_samples",
        "ck_soil_samples_hydrogen_saturation_range",
        "hydrogen_saturation_pct IS NULL OR hydrogen_saturation_pct BETWEEN 0 AND 100",
    ),
    (
        "soil_samples",
        "ck_soil_samples_sodium_saturation_range",
        "sodium_saturation_pct IS NULL OR sodium_saturation_pct BETWEEN 0 AND 100",
    ),
)


def upgrade() -> None:
    for table, name, expression in CONSTRAINTS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression}) NOT VALID"
        )


def downgrade() -> None:
    for table, name, _ in reversed(CONSTRAINTS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
