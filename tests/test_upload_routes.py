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
