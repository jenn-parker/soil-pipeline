import asyncio
import io
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from sqlalchemy import delete, select

from app.api import routes
from app.auth import Principal
from app.database import async_session_factory
from app.models.batch import SoilSampleBatch
from app.models.soil import SoilTestResult
from app.services.object_storage import discard_batch_upload, _get_s3_client

pytestmark = pytest.mark.integration


def test_real_postgres_and_localstack_complete_csv_upload() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run service integration tests")

    sample_id = f"INTEGRATION-{uuid.uuid4().hex[:16]}"
    content = f"sample_id,latitude,longitude,soil_ph\n{sample_id},42.7,-92.4,6.5\n"
    request = SimpleNamespace(
        state=SimpleNamespace(
            principal=Principal(subject="integration-test", scopes=frozenset())
        )
    )
    batch_id: int | None = None
    source_bucket: str | None = None
    source_key: str | None = None

    async def scenario() -> None:
        nonlocal batch_id, source_bucket, source_key
        async with async_session_factory() as db:
            batch = await routes.upload_soil_batch(
                request,
                UploadFile(
                    filename="integration.csv",
                    file=io.BytesIO(content.encode("utf-8")),
                ),
                db,
            )
            batch_id = batch.id
            source_bucket = batch.source_bucket
            source_key = batch.source_key

            stored_sample = await db.scalar(
                select(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
            )
            assert stored_sample is not None
            assert stored_sample.batch_id == batch.id
            assert batch.source_bucket == os.getenv("S3_BATCH_BUCKET", "soil-pipeline-batches")
            assert batch.source_key is not None

            # This is a real S3-compatible request, not a mocked storage call.
            _get_s3_client().head_object(Bucket=batch.source_bucket, Key=batch.source_key)

        assert batch_id is not None
        assert source_bucket is not None
        assert source_key is not None

        async with async_session_factory() as cleanup_db:
            await cleanup_db.execute(
                delete(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
            )
            await cleanup_db.execute(
                delete(SoilSampleBatch).where(SoilSampleBatch.id == batch_id)
            )
            await cleanup_db.commit()
        await discard_batch_upload(source_bucket, source_key)

    asyncio.run(scenario())
