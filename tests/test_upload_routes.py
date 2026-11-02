import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.api import routes
from app.auth import Principal


def request_for_owner() -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(principal=Principal(subject="owner-sub", scopes=frozenset())))


def upload(filename: str, contents: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(contents.encode("utf-8")))


def configured_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_upload_rejects_missing_header_and_invalid_rows() -> None:
    db = configured_db()
    with pytest.raises(HTTPException, match="sample_id header"):
        asyncio.run(routes.upload_soil_batch(request_for_owner(), upload("missing.csv", "field_name\nNorth\n"), db))

    monkeypatch_archive = AsyncMock(return_value=("bucket", "key"))
    original_archive = routes.archive_batch_upload
    routes.archive_batch_upload = monkeypatch_archive
    try:
        batch = asyncio.run(
            routes.upload_soil_batch(
                request_for_owner(),
                upload("invalid.csv", "sample_id,latitude\nBAD,not-a-number\n"),
                db,
            )
        )
    finally:
        routes.archive_batch_upload = original_archive

    assert batch.status == "rejected"
    assert batch.rejected_rows == 1
    monkeypatch_archive.assert_awaited_once()


def test_upload_accepts_valid_rows_and_assigns_owner() -> None:
    db = configured_db()
    db.scalars = AsyncMock(side_effect=[SimpleNamespace(all=lambda: []), SimpleNamespace(all=lambda: [])])
    archive = AsyncMock(return_value=("bucket", "soil-batches/key.csv"))
    original_archive = routes.archive_batch_upload
    routes.archive_batch_upload = archive
    try:
        batch = asyncio.run(
            routes.upload_soil_batch(
                request_for_owner(),
                upload("valid.csv", "sample_id,latitude,longitude,soil_ph\nFIELD-8,42.7,-92.4,6.5\n"),
                db,
            )
        )
    finally:
        routes.archive_batch_upload = original_archive

    assert batch.status == "completed"
    assert batch.accepted_rows == 1
    db.add_all.assert_called_once()
    created = db.add_all.call_args.args[0][0]
    assert created.created_by_sub == "owner-sub"
    archive.assert_awaited_once()
    db.commit.assert_awaited_once()


def test_upload_retains_archive_when_database_commit_outcome_is_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = configured_db()
    db.scalars = AsyncMock(side_effect=[SimpleNamespace(all=lambda: []), SimpleNamespace(all=lambda: [])])
    archive = AsyncMock(return_value=("bucket", "soil-batches/key.csv"))
    discard = AsyncMock()
    db.commit.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(routes, "archive_batch_upload", archive)
    monkeypatch.setattr(routes, "discard_batch_upload", discard)

    with pytest.raises(HTTPException, match="could not be saved"):
        asyncio.run(
            routes.upload_soil_batch(
                request_for_owner(),
                upload("valid.csv", "sample_id,latitude,longitude,soil_ph\nFIELD-8,42.7,-92.4,6.5\n"),
                db,
            )
        )

    # The commit may have succeeded before its confirmation was lost. The
    # archive must be retained so committed rows cannot reference a deleted
    # object.
    db.rollback.assert_awaited_once()
    discard.assert_not_awaited()


def test_upload_cleans_up_when_s3_archive_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = configured_db()
    db.scalars = AsyncMock(side_effect=[SimpleNamespace(all=lambda: []), SimpleNamespace(all=lambda: [])])
    archive = AsyncMock(side_effect=RuntimeError("S3 unavailable"))
    discard = AsyncMock()
    monkeypatch.setenv("S3_BATCH_BUCKET", "test-batches")
    monkeypatch.setattr(routes, "archive_batch_upload", archive)
    monkeypatch.setattr(routes, "discard_batch_upload", discard)

    with pytest.raises(HTTPException, match="storage is temporarily unavailable") as error:
        asyncio.run(
            routes.upload_soil_batch(
                request_for_owner(),
                upload("valid.csv", "sample_id,latitude,longitude,soil_ph\nFIELD-8,42.7,-92.4,6.5\n"),
                db,
            )
        )

    assert error.value.status_code == 503
    archive.assert_awaited_once()
    discard.assert_awaited_once()
    bucket, object_key = discard.await_args.args
    assert bucket == "test-batches"
    assert object_key.startswith("soil-batches/")
    assert object_key.endswith("/valid.csv")
    db.commit.assert_not_awaited()
