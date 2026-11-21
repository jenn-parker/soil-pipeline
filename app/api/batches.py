import csv
import io
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from time import perf_counter

from fastapi import Depends, File, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import _principal, make_wgs84_point
from app.api.router import router
from app.auth import require_scope
from app.database import get_db_session
from app.models.batch import SoilSampleBatch
from app.models.sample import SampleProvenance
from app.models.soil import SoilTestResult
from app.schemas.batch import SoilSampleBatchRead
from app.schemas.soil import SoilTestResultCreate
from app.services.object_storage import archive_batch_upload, discard_batch_upload
from app.services.batch_state import (
    transition_archive_status,
    transition_batch_status,
    validate_archive_status_transition,
    validate_batch_status_transition,
)

logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ARCHIVE_LEASE_DURATION = timedelta(hours=2)

@router.post(
    "/soil-batches",
    tags=["File batches"],
    summary="Upload a CSV batch of soil samples",
    description=(
        "Upload a UTF-8 CSV file with a `sample_id` header. All rows are validated "
        "before any samples are saved; the response includes row-level errors if rejected."
    ),
    response_model=SoilSampleBatchRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("batch:upload"))],
)
async def upload_soil_batch(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> SoilSampleBatch:
    started_at = perf_counter()
    filename = (file.filename or "upload.csv").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    logger.info(
        "batch.upload.started",
        extra={"upload_filename": filename, "upload_size_bytes": len(contents)},
    )
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV uploads must be 10 MB or smaller")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Upload must be a UTF-8 encoded CSV") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if not reader.fieldnames or "sample_id" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must include a sample_id header")
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise HTTPException(status_code=400, detail="CSV contains duplicate column headers")

    valid_samples: list[tuple[int, SoilTestResultCreate]] = []
    row_errors: list[dict[str, object]] = []
    sample_ids: set[str] = set()
    total_rows = 0
    try:
        for row in reader:
            row_number = reader.line_num
            if not row or not any(value and value.strip() for value in row.values() if isinstance(value, str)):
                continue
            total_rows += 1
            try:
                if None in row:
                    raise ValueError("row contains more values than the CSV header")
                sample = SoilTestResultCreate.model_validate(row)
                if not sample.sample_id.strip():
                    raise ValueError("sample_id must not be blank")
                if sample.sample_id in sample_ids:
                    raise ValueError("sample_id is duplicated within this file")
                sample_ids.add(sample.sample_id)
                valid_samples.append((row_number, sample))
            except (ValidationError, ValueError) as exc:
                if isinstance(exc, ValidationError):
                    details = [
                        {
                            "field": ".".join(str(part) for part in error["loc"]),
                            "message": error["msg"],
                            "type": error["type"],
                        }
                        for error in exc.errors()
                    ]
                else:
                    details = [{"field": "sample_id", "message": str(exc), "type": "invalid"}]
                row_errors.append({"row": row_number, "errors": details})
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail="CSV file could not be parsed") from exc

    if total_rows == 0:
        raise HTTPException(status_code=400, detail="CSV contains no sample rows")

    if not row_errors:
        existing_ids = set(
            (await db.scalars(select(SoilTestResult.sample_id).where(SoilTestResult.sample_id.in_(sample_ids)))).all()
        )
        if existing_ids:
            for row_number, sample in valid_samples:
                if sample.sample_id in existing_ids:
                    row_errors.append({
                        "row": row_number,
                        "errors": [{
                            "field": "sample_id",
                            "message": "sample_id already exists",
                            "type": "duplicate",
                        }],
                    })

    provenance_by_sample_id: dict[str, SampleProvenance] = {}
    if not row_errors:
        provenance_records = (
            await db.scalars(
                select(SampleProvenance).where(
                    SampleProvenance.sample_id.in_(sample_ids)
                )
            )
        ).all()
        provenance_by_sample_id = {
            provenance.sample_id: provenance
            for provenance in provenance_records
        }
        for _, sample in valid_samples:
            provenance = provenance_by_sample_id.get(sample.sample_id)
            if provenance is not None and provenance.soil_sample_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Sample provenance {sample.sample_id} is already linked to a soil test record",
                )

    accepted_rows = 0 if row_errors else len(valid_samples)
    logger.info(
        "batch.validation.completed",
        extra={
            "upload_filename": filename,
            "total_rows": total_rows,
            "accepted_rows": accepted_rows,
            "rejected_rows": total_rows - accepted_rows,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )
    bucket = os.getenv("S3_BATCH_BUCKET", "soil-pipeline-batches")
    generation = uuid.uuid4().hex
    object_key = f"soil-batches/{generation}/{filename}"
    lease_until = datetime.now(timezone.utc) + ARCHIVE_LEASE_DURATION
    batch = SoilSampleBatch(
        filename=filename,
        created_by_sub=_principal(request).subject,
        status="processing",
        total_rows=total_rows,
        accepted_rows=accepted_rows,
        rejected_rows=total_rows - accepted_rows,
        errors=row_errors,
        source_bucket=bucket,
        source_key=object_key,
        archive_status="pending",
        archive_generation=generation,
        archive_lease_until=lease_until,
    )
    db.add(batch)
    await db.flush()
    batch_id = batch.id

    try:
        await db.commit()
    except Exception as exc:
        logger.exception("batch.intent_commit.failed", extra={"batch_id": batch_id, "upload_filename": filename})
        try:
            await db.rollback()
        except Exception:
            logger.exception("batch.rollback.failed", extra={"batch_id": batch_id})
        raise HTTPException(status_code=503, detail="Batch could not be prepared") from exc

    archived_object: tuple[str, str] | None = None
    try:
        archived_object = await archive_batch_upload(contents=contents, object_key=object_key)
    except RuntimeError as exc:
        logger.exception("batch.archive.failed", extra={"batch_id": batch_id, "upload_filename": filename})
        # A successful PUT can still be reported as failed (for example, if the
        # response is lost), so remove the key even when archive_batch_upload
        # raises before returning it.
        try:
            await discard_batch_upload(bucket, object_key)
        except RuntimeError:
            pass
        try:
            await db.refresh(batch)
            transition_archive_status(batch, "failed")
            transition_batch_status(batch, "failed")
            batch.archive_lease_until = None
            batch.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception:
            logger.exception("batch.archive_failure_state_commit.failed", extra={"batch_id": batch_id})
        raise HTTPException(status_code=503, detail="Batch file storage is temporarily unavailable") from exc

    try:
        await db.refresh(batch, with_for_update=True)
        if (
            batch.archive_status != "pending"
            or batch.archive_generation != generation
            or batch.archive_lease_until is None
            or batch.archive_lease_until <= datetime.now(timezone.utc)
        ):
            # Another worker may already have finalized or fenced this
            # generation. A stale uploader must not overwrite that decision.
            batch_id = batch.id
            await db.rollback()
            logger.warning(
                "batch.archive.uploader_fenced",
                extra={"batch_id": batch_id, "upload_filename": filename},
            )
            raise HTTPException(status_code=409, detail="Batch upload lease is no longer valid")

        soil_rows: list[SoilTestResult] = []
        linked_rows: list[tuple[SampleProvenance, SoilTestResult]] = []
        for _, sample in valid_samples:
            provenance = provenance_by_sample_id.get(sample.sample_id)
            latitude, longitude = sample.latitude, sample.longitude
            if (
                (latitude is None or longitude is None)
                and provenance is not None
                and provenance.latitude is not None
                and provenance.longitude is not None
            ):
                latitude, longitude = float(provenance.latitude), float(provenance.longitude)
            sample_data = sample.model_dump()
            sample_data.update(
                batch_id=batch.id,
                latitude=latitude,
                longitude=longitude,
                location=make_wgs84_point(latitude, longitude),
                created_by_sub=_principal(request).subject,
            )
            soil_row = SoilTestResult(**sample_data)
            soil_rows.append(soil_row)
            if provenance is not None:
                linked_rows.append((provenance, soil_row))
        db.add_all(soil_rows)
        await db.flush()

        provenance_updates = {provenance.id: soil_row.id for provenance, soil_row in linked_rows}
        if provenance_updates:
            await db.execute(
                update(SampleProvenance)
                .where(SampleProvenance.id.in_(provenance_updates))
                .values(soil_sample_id=case(provenance_updates, value=SampleProvenance.id))
                .execution_options(synchronize_session=False)
            )

        final_status = "rejected" if row_errors else "completed"
        final_time = datetime.now(timezone.utc)
        validate_archive_status_transition(batch.archive_status, "archived")
        validate_batch_status_transition(batch.status, final_status)
        finalization = await db.execute(
            update(SoilSampleBatch)
            .where(
                SoilSampleBatch.id == batch.id,
                SoilSampleBatch.archive_status == "pending",
                SoilSampleBatch.archive_generation == generation,
                SoilSampleBatch.archive_lease_until > final_time,
            )
            .values(
                status=final_status,
                completed_at=final_time,
                archive_lease_until=None,
                archive_fenced_at=None,
                archive_fence_reason=None,
            )
            .execution_options(synchronize_session=False)
        )
        if finalization.rowcount != 1:
            await db.rollback()
            logger.warning(
                "batch.archive.finalization_fenced",
                extra={"batch_id": batch.id, "upload_filename": filename},
            )
            raise HTTPException(status_code=409, detail="Batch upload lease is no longer valid")
        await db.commit()
        # Reflect the committed transition in the ORM object only after the
        # commit succeeds; an ambiguous commit must leave the in-memory state
        # at the safe pending value.
        transition_archive_status(batch, "archived")
        transition_batch_status(batch, final_status)
        await db.refresh(batch)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("batch.database_commit.failed", extra={"batch_id": batch_id, "upload_filename": filename})
        # The commit outcome is ambiguous when the connection drops after
        # PostgreSQL commits but before the client receives confirmation. Do
        # not delete the archive: the durable pending lease protects it and
        # reconciliation can resolve the state after the lease expires.
        if archived_object is not None:
            logger.error(
                "batch.archive.retained_after_ambiguous_commit",
                extra={
                    "batch_id": batch_id,
                    "s3_bucket": archived_object[0],
                    "s3_key": archived_object[1],
                },
            )
        try:
            await db.rollback()
        except Exception:
            logger.exception("batch.rollback.failed", extra={"batch_id": batch_id})
        raise HTTPException(status_code=503, detail="Batch could not be saved") from exc

    logger.info(
        "batch.completed",
        extra={
            "batch_id": batch.id,
            "status": batch.status,
            "total_rows": batch.total_rows,
            "accepted_rows": batch.accepted_rows,
            "rejected_rows": batch.rejected_rows,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )
    return batch



@router.get(
    "/soil-batches/{batch_id}",
    tags=["File batches"],
    summary="Get a soil batch result",
    response_model=SoilSampleBatchRead,
)
async def get_soil_batch(
    batch_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> SoilSampleBatch:
    batch = await db.scalar(
        select(SoilSampleBatch).where(
            SoilSampleBatch.id == batch_id,
            SoilSampleBatch.created_by_sub == _principal(request).subject,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Soil upload batch not found")
    return batch

