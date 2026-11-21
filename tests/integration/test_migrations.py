import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.database import engine

pytestmark = pytest.mark.integration


def test_alembic_upgrade_head_matches_live_schema() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run service integration tests")

    async def dispose() -> None:
        await engine.dispose()

    asyncio.run(dispose())
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    expected_head = ScriptDirectory.from_config(config).get_current_head()

    async def inspect_schema() -> tuple[str, set[str], set[str]]:
        async with engine.connect() as connection:
            revision = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
            columns = {
                row[0]
                for row in (
                    await connection.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name IN ('soil_upload_batches', 'soil_sample_access')
                            """
                        )
                    )
                ).all()
            }
            constraints = {
                row[0]
                for row in (
                    await connection.execute(
                        text(
                            """
                            SELECT conname
                            FROM pg_constraint
                            WHERE conname LIKE 'ck_soil_%'
                               OR conname LIKE 'ck_sample_%'
                            """
                        )
                    )
                ).all()
            }
        return revision, columns, constraints

    revision, columns, constraints = asyncio.run(inspect_schema())
    assert revision == expected_head
    assert {"created_by_sub"} <= columns
    assert {"user_sub"} <= columns
    assert {
        "ck_soil_upload_batches_final_row_counts",
        "ck_soil_samples_coordinate_pair",
        "ck_sample_identifications_coordinate_pair",
        "ck_soil_samples_nitrate_nonnegative",
    } <= constraints
