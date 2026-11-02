import asyncio
import io
import os
import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, UploadFile
from botocore.exceptions import ClientError
from sqlalchemy import delete, select, update

from app.api import routes
from app.auth import Principal
from app.database import async_session_factory, engine
from app.models.batch import SoilSampleBatch
from app.models.soil import SoilTestResult
from app.services.object_storage import discard_batch_upload, _get_s3_client
from app.services import object_storage
from app.jobs.reconcile_batch_archives import reconcile_batch_archives

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def dispose_database_engine_between_event_loops():
    yield
    asyncio.run(engine.dispose())


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
        try:
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
        finally:
            if batch_id is not None:
                async with async_session_factory() as cleanup_db:
                    await cleanup_db.execute(
                        delete(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
                    )
                    await cleanup_db.execute(
                        delete(SoilSampleBatch).where(SoilSampleBatch.id == batch_id)
                    )
                    await cleanup_db.commit()
            if source_bucket is not None and source_key is not None:
                await discard_batch_upload(source_bucket, source_key)

    asyncio.run(scenario())


def test_real_postgres_rejects_invalid_csv_without_samples() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run service integration tests")

    sample_id = f"INTEGRATION-REJECTED-{uuid.uuid4().hex[:12]}"
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
        try:
            async with async_session_factory() as db:
                batch = await routes.upload_soil_batch(
                    request,
                    UploadFile(
                        filename="rejected.csv",
                        file=io.BytesIO(
                            f"sample_id,latitude\n{sample_id},not-a-number\n".encode("utf-8")
                        ),
                    ),
                    db,
                )
                batch_id = batch.id
                source_bucket = batch.source_bucket
                source_key = batch.source_key
                assert batch.status == "rejected"
                assert await db.scalar(
                    select(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
                ) is None
                _get_s3_client().head_object(Bucket=source_bucket, Key=source_key)
        finally:
            if batch_id is not None:
                async with async_session_factory() as cleanup_db:
                    await cleanup_db.execute(
                        delete(SoilSampleBatch).where(SoilSampleBatch.id == batch_id)
                    )
                    await cleanup_db.commit()
            if source_bucket is not None and source_key is not None:
                await discard_batch_upload(source_bucket, source_key)

    asyncio.run(scenario())


def test_real_s3_failure_persists_failed_archive_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run service integration tests")

    sample_id = f"INTEGRATION-S3-FAIL-{uuid.uuid4().hex[:12]}"
    filename = f"storage-failure-{uuid.uuid4().hex[:12]}.csv"
    request = SimpleNamespace(
        state=SimpleNamespace(
            principal=Principal(subject="integration-test", scopes=frozenset())
        )
    )
    original_endpoint = os.getenv("AWS_ENDPOINT_URL_S3")
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "http://127.0.0.1:1")

    async def scenario() -> None:
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as error:
                await routes.upload_soil_batch(
                    request,
                    UploadFile(
                            filename=filename,
                        file=io.BytesIO(
                            f"sample_id,latitude,longitude\n{sample_id},42.7,-92.4\n".encode("utf-8")
                        ),
                    ),
                    db,
                )
            assert error.value.status_code == 503

        async with async_session_factory() as verification_db:
            assert await verification_db.scalar(
                select(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
            ) is None
            failed_batch = await verification_db.scalar(
                select(SoilSampleBatch).where(SoilSampleBatch.filename == filename)
            )
            assert failed_batch is not None
            assert failed_batch.status == "failed"
            assert failed_batch.archive_status == "failed"
            await verification_db.execute(
                delete(SoilSampleBatch).where(SoilSampleBatch.id == failed_batch.id)
            )
            await verification_db.commit()

    try:
        asyncio.run(scenario())
    finally:
        if original_endpoint is None:
            monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
        else:
            monkeypatch.setenv("AWS_ENDPOINT_URL_S3", original_endpoint)


def test_real_reconciliation_deletes_old_orphan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run service integration tests")

    bucket = f"soil-pipeline-reconcile-{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("S3_BATCH_BUCKET", bucket)
    object_key = f"soil-batches/integration-orphan-{uuid.uuid4().hex}.csv"
    client = _get_s3_client()
    client.create_bucket(Bucket=bucket)
    client.put_object(Bucket=bucket, Key=object_key, Body=b"orphan")

    async def scenario() -> None:
        async with async_session_factory() as db:
            result = await reconcile_batch_archives(
                db,
                grace_period=timedelta(days=1),
                now=datetime.now(timezone.utc) + timedelta(days=2),
            )
            assert result.deleted >= 1

    try:
        asyncio.run(scenario())
        with pytest.raises(ClientError):
            client.head_object(Bucket=bucket, Key=object_key)
    finally:
        try:
            asyncio.run(discard_batch_upload(bucket, object_key))
        except RuntimeError:
            pass
        client.delete_bucket(Bucket=bucket)


def test_real_expired_lease_fences_stale_uploader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run service integration tests")

    bucket = f"soil-pipeline-race-{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("S3_BATCH_BUCKET", bucket)
    client = _get_s3_client()
    client.create_bucket(Bucket=bucket)
    sample_id = f"INTEGRATION-RACE-{uuid.uuid4().hex[:12]}"
    filename = f"race-{uuid.uuid4().hex[:12]}.csv"
    request = SimpleNamespace(
        state=SimpleNamespace(
            principal=Principal(subject="integration-test", scopes=frozenset())
        )
    )
    put_finished = asyncio.Event()
    release_uploader = asyncio.Event()
    batch_id: int | None = None
    source_bucket: str | None = None
    source_key: str | None = None

    async def gated_archive(contents: bytes, object_key: str) -> tuple[str, str]:
        result = await object_storage.archive_batch_upload(contents, object_key)
        put_finished.set()
        await release_uploader.wait()
        return result

    monkeypatch.setattr(routes, "archive_batch_upload", gated_archive)

    async def scenario() -> None:
        nonlocal batch_id, source_bucket, source_key
        upload_task: asyncio.Task[object] | None = None
        try:
            async with async_session_factory() as upload_db:
                upload_task = asyncio.create_task(
                    routes.upload_soil_batch(
                        request,
                        UploadFile(
                            filename=filename,
                            file=io.BytesIO(
                                f"sample_id,latitude,longitude\n{sample_id},42.7,-92.4\n".encode("utf-8")
                            ),
                        ),
                        upload_db,
                    )
                )
                await put_finished.wait()

                async with async_session_factory() as lease_db:
                    pending_batch = await lease_db.scalar(
                        select(SoilSampleBatch).where(SoilSampleBatch.filename == filename)
                    )
                    assert pending_batch is not None
                    batch_id = pending_batch.id
                    source_bucket = pending_batch.source_bucket
                    source_key = pending_batch.source_key
                    await lease_db.execute(
                        update(SoilSampleBatch)
                        .where(SoilSampleBatch.id == pending_batch.id)
                        .values(archive_lease_until=datetime.now(timezone.utc) - timedelta(minutes=1))
                    )
                    await lease_db.commit()

                async with async_session_factory() as reconcile_db:
                    await reconcile_batch_archives(
                        reconcile_db,
                        grace_period=timedelta(days=1),
                        now=datetime.now(timezone.utc) + timedelta(days=2),
                    )

                release_uploader.set()
                with pytest.raises(HTTPException, match="lease is no longer valid"):
                    await upload_task
                assert await upload_db.scalar(
                    select(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
                ) is None
                fenced_batch = await upload_db.scalar(
                    select(SoilSampleBatch).where(SoilSampleBatch.id == batch_id)
                )
                assert fenced_batch is not None
                assert fenced_batch.archive_status == "abandoned"
                assert fenced_batch.archive_fenced_at is not None
                assert fenced_batch.archive_fence_reason == "lease_expired"
        finally:
            release_uploader.set()
            if upload_task is not None and not upload_task.done():
                upload_task.cancel()
                await asyncio.gather(upload_task, return_exceptions=True)
            if batch_id is not None:
                async with async_session_factory() as cleanup_db:
                    await cleanup_db.execute(
                        delete(SoilTestResult).where(SoilTestResult.sample_id == sample_id)
                    )
                    await cleanup_db.execute(
                        delete(SoilSampleBatch).where(SoilSampleBatch.id == batch_id)
                    )
                    await cleanup_db.commit()
            if source_bucket is not None and source_key is not None:
                try:
                    await discard_batch_upload(source_bucket, source_key)
                except RuntimeError:
                    pass
            client.delete_bucket(Bucket=bucket)

    asyncio.run(scenario())
