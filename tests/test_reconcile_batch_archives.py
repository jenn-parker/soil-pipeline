from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.jobs import reconcile_batch_archives as reconciliation


def test_reconciliation_deletes_only_old_unreferenced_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    objects = [
        {"Key": "soil-batches/referenced.csv", "LastModified": now - timedelta(days=30)},
        {"Key": "soil-batches/recent.csv", "LastModified": now - timedelta(hours=2)},
        {"Key": "soil-batches/orphan.csv", "LastModified": now - timedelta(days=2)},
    ]
    list_objects = AsyncMock(return_value=objects)
    discard = AsyncMock()
    referenced_batch = SimpleNamespace(
        id=1,
        source_key="soil-batches/referenced.csv",
        archive_status="archived",
        archive_lease_until=None,
    )
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: ["soil-batches/referenced.csv"])),
        scalar=AsyncMock(side_effect=[referenced_batch, None]),
        commit=AsyncMock(),
    )
    monkeypatch.setenv("S3_BATCH_BUCKET", "test-batches")
    monkeypatch.setattr(reconciliation, "list_batch_objects", list_objects)
    monkeypatch.setattr(reconciliation, "discard_batch_upload", discard)

    result = __import__("asyncio").run(
        reconciliation.reconcile_batch_archives(
            db,
            grace_period=timedelta(days=1),
            now=now,
        )
    )

    assert result.scanned == 3
    assert result.referenced == 1
    assert result.too_recent == 1
    assert result.deleted == 1
    assert result.delete_failures == 0
    discard.assert_awaited_once_with("test-batches", "soil-batches/orphan.csv")


def test_reconciliation_fails_closed_when_object_timestamp_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_objects = AsyncMock(return_value=[{"Key": "soil-batches/unknown.csv"}])
    discard = AsyncMock()
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
        scalar=AsyncMock(return_value=None),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(reconciliation, "list_batch_objects", list_objects)
    monkeypatch.setattr(reconciliation, "discard_batch_upload", discard)

    result = __import__("asyncio").run(
        reconciliation.reconcile_batch_archives(db, now=datetime.now(timezone.utc))
    )

    assert result.too_recent == 1
    discard.assert_not_awaited()


def test_reconciliation_abandons_expired_pending_lease_before_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    pending_batch = SimpleNamespace(
        id=2,
        source_key="soil-batches/expired.csv",
        archive_status="pending",
        archive_lease_until=now - timedelta(hours=1),
    )
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: ["soil-batches/expired.csv"])),
        scalar=AsyncMock(side_effect=[pending_batch, pending_batch, pending_batch]),
        commit=AsyncMock(),
    )
    discard = AsyncMock()
    monkeypatch.setattr(
        reconciliation,
        "list_batch_objects",
        AsyncMock(return_value=[
            {"Key": "soil-batches/expired.csv", "LastModified": now - timedelta(days=2)}
        ]),
    )
    monkeypatch.setattr(reconciliation, "discard_batch_upload", discard)

    result = __import__("asyncio").run(
        reconciliation.reconcile_batch_archives(db, now=now)
    )

    assert pending_batch.archive_status == "abandoned"
    assert result.deleted == 1
    db.commit.assert_awaited_once()
    discard.assert_awaited_once_with("soil-pipeline-batches", "soil-batches/expired.csv")


def test_reconciliation_retains_active_pending_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    active_batch = SimpleNamespace(
        id=3,
        source_key="soil-batches/active.csv",
        archive_status="pending",
        archive_lease_until=now + timedelta(hours=1),
    )
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: ["soil-batches/active.csv"])),
        scalar=AsyncMock(return_value=active_batch),
        commit=AsyncMock(),
    )
    discard = AsyncMock()
    monkeypatch.setattr(
        reconciliation,
        "list_batch_objects",
        AsyncMock(return_value=[
            {"Key": "soil-batches/active.csv", "LastModified": now - timedelta(days=2)}
        ]),
    )
    monkeypatch.setattr(reconciliation, "discard_batch_upload", discard)

    result = __import__("asyncio").run(
        reconciliation.reconcile_batch_archives(db, now=now)
    )

    assert result.referenced == 1
    assert result.deleted == 0
    db.commit.assert_not_awaited()
    discard.assert_not_awaited()
