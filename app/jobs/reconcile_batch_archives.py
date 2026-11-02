"""Remove old S3 batch archives that PostgreSQL does not reference."""

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.batch import SoilSampleBatch
from app.services.object_storage import discard_batch_upload, list_batch_objects

logger = logging.getLogger(__name__)
BATCH_ARCHIVE_PREFIX = "soil-batches/"


@dataclass(frozen=True)
class ReconciliationResult:
    scanned: int = 0
    referenced: int = 0
    too_recent: int = 0
    deleted: int = 0
    delete_failures: int = 0


def _as_utc(value: datetime) -> datetime | None:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def reconcile_batch_archives(
    db: AsyncSession,
    *,
    grace_period: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> ReconciliationResult:
    """Delete stale, unreferenced batch archives after a safety grace period."""
    if grace_period <= timedelta(0):
        raise ValueError("grace_period must be positive")

    bucket = os.getenv("S3_BATCH_BUCKET", "soil-pipeline-batches")
    current_time = _as_utc(now or datetime.now(timezone.utc))
    assert current_time is not None
    cutoff = current_time - grace_period
    objects = await list_batch_objects(bucket, BATCH_ARCHIVE_PREFIX)

    referenced_keys = {
        key
        for key in (
            await db.scalars(
                select(SoilSampleBatch.source_key).where(
                    SoilSampleBatch.source_bucket == bucket,
                    SoilSampleBatch.source_key.is_not(None),
                )
            )
        ).all()
        if key is not None
    }

    result = ReconciliationResult(scanned=len(objects), referenced=0)
    for item in objects:
        object_key = item.get("Key")
        last_modified = item.get("LastModified")
        if not isinstance(object_key, str) or not object_key.startswith(BATCH_ARCHIVE_PREFIX):
            continue
        if object_key in referenced_keys:
            result = ReconciliationResult(
                scanned=result.scanned,
                referenced=result.referenced + 1,
                too_recent=result.too_recent,
                deleted=result.deleted,
                delete_failures=result.delete_failures,
            )
            continue
        modified_at = _as_utc(last_modified) if isinstance(last_modified, datetime) else None
        if modified_at is None or modified_at >= cutoff:
            result = ReconciliationResult(
                scanned=result.scanned,
                referenced=result.referenced,
                too_recent=result.too_recent + 1,
                deleted=result.deleted,
                delete_failures=result.delete_failures,
            )
            continue
        try:
            await discard_batch_upload(bucket, object_key)
        except RuntimeError:
            logger.exception(
                "batch.archive.reconciliation_delete_failed",
                extra={"s3_bucket": bucket, "s3_key": object_key},
            )
            result = ReconciliationResult(
                scanned=result.scanned,
                referenced=result.referenced,
                too_recent=result.too_recent,
                deleted=result.deleted,
                delete_failures=result.delete_failures + 1,
            )
        else:
            logger.info(
                "batch.archive.reconciled",
                extra={"s3_bucket": bucket, "s3_key": object_key},
            )
            result = ReconciliationResult(
                scanned=result.scanned,
                referenced=result.referenced,
                too_recent=result.too_recent,
                deleted=result.deleted + 1,
                delete_failures=result.delete_failures,
            )
    return result


async def _run(grace_hours: float) -> ReconciliationResult:
    async with async_session_factory() as db:
        result = await reconcile_batch_archives(
            db,
            grace_period=timedelta(hours=grace_hours),
        )
        await db.rollback()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=24.0,
        help="Do not delete unreferenced objects newer than this many hours (default: 24).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    result = asyncio.run(_run(args.grace_hours))
    logger.info("batch.archive.reconciliation_completed", extra={"reconciliation": result.__dict__})


if __name__ == "__main__":
    main()
