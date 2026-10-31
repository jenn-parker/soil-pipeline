import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from time import perf_counter

from geoalchemy2 import Geography, Geometry
from geoalchemy2.elements import WKTElement
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import case, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db_session
from app.auth import require_scope
from app.models.batch import SoilSampleBatch
from app.models.sample import Party, SampleProvenance
from app.models.soil import SoilTestResult
from app.schemas.batch import SoilSampleBatchRead
from app.schemas.geojson import (
    GeoJSONPoint,
    SoilSampleFeature,
    SoilSampleFeatureCollection,
    SoilSampleProperties,
)
from app.schemas.sample import (
    PartyCreate,
    PartyRead,
    SampleProvenanceCreate,
    SampleProvenanceRead,
)
from app.schemas.report import MeasurementRange, SoilRangeReport
from app.schemas.recommendation import (
    LocationRecommendationRequest,
    LocationRecommendationResponse,
)
from app.schemas.soil import SoilTestResultCreate, SoilTestResultRead
from app.services.recommendations import (
    explain_soil_summary,
    missing_recommendation_context,
    build_recommendation_guidance,
)
from app.services.object_storage import archive_batch_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_scope("soil:read"))])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SOIL_MEASUREMENTS = (
    "soil_ph",
    "buffer_ph",
    "organic_matter_pct",
    "cation_exchange_capacity",
    "electrical_conductivity",
    "nitrate_nitrogen_ppm",
    "phosphorus_ppm",
    "potassium_ppm",
    "sulfur_ppm",
    "calcium_ppm",
    "magnesium_ppm",
    "sodium_ppm",
    "zinc_ppm",
    "iron_ppm",
    "manganese_ppm",
    "copper_ppm",
    "boron_ppm",
    "sand_pct",
    "silt_pct",
    "clay_pct",
    "bulk_density_g_cm3",
    "calcium_saturation_pct",
    "magnesium_saturation_pct",
    "potassium_saturation_pct",
    "hydrogen_saturation_pct",
    "sodium_saturation_pct",
)
SOIL_MEASUREMENT_ATTRIBUTES = {
    "cation_exchange_capacity": "cation_exchange_capacity_meq_per_100g",
    "electrical_conductivity": "electrical_conductivity_ds_m",
}


def make_wgs84_point(latitude: float | None, longitude: float | None) -> WKTElement | None:
    if latitude is None or longitude is None:
        return None
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


@router.get(
    "/reports/soil-ranges",
    tags=["Reports"],
    summary="Summarize soil samples near a location",
    description=(
        "Returns sample count, sampled date range, and per-measurement minimum and "
        "maximum values for samples within the requested radius. Does not return individual samples."
    ),
    response_model=SoilRangeReport,
)
async def get_soil_range_report(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(..., gt=0, le=1000),
    db: AsyncSession = Depends(get_db_session),
) -> SoilRangeReport:
    center_point = cast(
        make_wgs84_point(latitude, longitude),
        Geography(geometry_type="POINT", srid=4326),
    )

    aggregates = [
        func.count(SoilTestResult.id).label("sample_count"),
        func.min(SoilTestResult.sampled_at).label("first_sampled_at"),
        func.max(SoilTestResult.sampled_at).label("last_sampled_at"),
    ]
    for name in SOIL_MEASUREMENTS:
        attribute_name = SOIL_MEASUREMENT_ATTRIBUTES.get(name, name)
        column = getattr(SoilTestResult, attribute_name)
        aggregates.extend(
            [
                func.count(column).label(f"{name}_count"),
                func.min(column).label(f"{name}_minimum"),
                func.max(column).label(f"{name}_maximum"),
            ]
        )

    result = await db.execute(
        select(*aggregates)
        .where(
            SoilTestResult.location.is_not(None),
            func.ST_DWithin(SoilTestResult.location, center_point, radius_km * 1000),
        )
    )
    row = result.mappings().one()
    measurements = {
        name: MeasurementRange(
            sample_count=row[f"{name}_count"],
            minimum=row[f"{name}_minimum"],
            maximum=row[f"{name}_maximum"],
        )
        for name in SOIL_MEASUREMENTS
        if row[f"{name}_count"] > 0
    }
    return SoilRangeReport(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        sample_count=row["sample_count"],
        first_sampled_at=row["first_sampled_at"],
        last_sampled_at=row["last_sampled_at"],
        measurements=measurements,
    )


@router.post(
    "/recommendations/location",
    tags=["Reports"],
    summary="Prepare a conservative recommendation brief for a location",
    description=(
        "Summarizes nearby soil data and identifies missing recommendation context. "
        "Optional AI text only explains the data; it never generates application rates."
    ),
    response_model=LocationRecommendationResponse,
)
async def create_location_recommendation_brief(
    request: LocationRecommendationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> LocationRecommendationResponse:
    soil_summary = await get_soil_range_report(
        request.latitude,
        request.longitude,
        request.radius_km,
        db,
    )
    missing_context = missing_recommendation_context(request)
    recommendation_status, guidance = build_recommendation_guidance(soil_summary, missing_context)

    ai_explanation = None
    if request.include_ai_explanation and soil_summary.sample_count > 0:
        try:
            ai_explanation = await explain_soil_summary(request, soil_summary, missing_context)
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 503 if "OPENAI_API_KEY" in detail else 502
            raise HTTPException(status_code=status_code, detail=detail) from exc

    return LocationRecommendationResponse(
        status=recommendation_status,
        soil_summary=soil_summary,
        missing_context=missing_context,
        guidance=guidance,
        ai_assisted=ai_explanation is not None,
        ai_explanation=ai_explanation,
    )


@router.get(
    "/maps/soil-samples",
    tags=["Mapping"],
    summary="Get soil sample locations as GeoJSON",
    description="Returns mapped soil samples within a longitude/latitude bounding box.",
    response_model=SoilSampleFeatureCollection,
)
async def get_soil_samples_geojson(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    limit: int = Query(1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db_session),
) -> SoilSampleFeatureCollection:
    if west >= east or south >= north:
        raise HTTPException(
            status_code=422,
            detail="Bounding box must have west < east and south < north",
        )

    bounding_box = cast(
        func.ST_MakeEnvelope(west, south, east, north, 4326),
        Geography(srid=4326),
    )
    point_geometry = cast(SoilTestResult.location, Geometry(srid=4326))
    longitude = func.ST_X(point_geometry).label("longitude")
    latitude = func.ST_Y(point_geometry).label("latitude")
    result = await db.execute(
        select(
            SoilTestResult.sample_id,
            SoilTestResult.field_name,
            SoilTestResult.sampled_at,
            SoilTestResult.soil_ph,
            SoilTestResult.organic_matter_pct,
            SoilTestResult.sand_pct,
            SoilTestResult.silt_pct,
            SoilTestResult.clay_pct,
            longitude,
            latitude,
        )
        .where(
            SoilTestResult.location.is_not(None),
            func.ST_Intersects(SoilTestResult.location, bounding_box),
        )
        .order_by(SoilTestResult.sample_id)
        .limit(limit)
    )
    features = [
        SoilSampleFeature(
            geometry=GeoJSONPoint(coordinates=(row.longitude, row.latitude)),
            properties=SoilSampleProperties(
                sample_id=row.sample_id,
                field_name=row.field_name,
                sampled_at=row.sampled_at,
                soil_ph=row.soil_ph,
                organic_matter_pct=row.organic_matter_pct,
                sand_pct=row.sand_pct,
                silt_pct=row.silt_pct,
                clay_pct=row.clay_pct,
            ),
        )
        for row in result
    ]
    return SoilSampleFeatureCollection(features=features)



@router.post(
    "/soil-samples",
    tags=["Soil samples"],
    summary="Create a soil test record",
    description="Create one soil test record from a JSON request body.",
    response_model=SoilTestResultRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def create_soil_test_result(
    sample: SoilTestResultCreate,
    db: AsyncSession = Depends(get_db_session),
) -> SoilTestResult:
    duplicate = await db.scalar(
        select(SoilTestResult.id).where(SoilTestResult.sample_id == sample.sample_id)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="A soil sample with this sample_id already exists")

    provenance = await db.scalar(
        select(SampleProvenance).where(
            SampleProvenance.sample_id == sample.sample_id
        )
    )
    if provenance is not None and provenance.soil_sample_id is not None:
        raise HTTPException(status_code=409, detail="This sample provenance record is already linked to a soil test result")

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
        latitude=latitude,
        longitude=longitude,
        location=make_wgs84_point(latitude, longitude),
    )
    db_sample = SoilTestResult(**sample_data)
    db.add(db_sample)
    await db.flush()
    if provenance is not None:
        provenance.soil_sample_id = db_sample.id
    await db.refresh(db_sample)
    return db_sample


@router.post(
    "/parties",
    tags=["Parties"],
    summary="Create a party",
    description="Create an owner or collector record.",
    response_model=PartyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def create_party(
    party: PartyCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Party:
    db_party = Party(**party.model_dump())
    db.add(db_party)
    await db.flush()
    await db.refresh(db_party)
    return db_party


@router.post(
    "/sample-identifications",
    tags=["Sample provenance"],
    summary="Create sample provenance details",
    response_model=SampleProvenanceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def create_sample_provenance(
    sample: SampleProvenanceCreate,
    db: AsyncSession = Depends(get_db_session),
) -> SampleProvenance:
    owner = await db.get(Party, sample.owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail=f"Owner party {sample.owner_id} was not found")
    if sample.collector_id is not None and await db.get(Party, sample.collector_id) is None:
        raise HTTPException(status_code=404, detail=f"Collector party {sample.collector_id} was not found")

    duplicate = await db.scalar(
        select(SampleProvenance.id).where(
            SampleProvenance.sample_id == sample.sample_id
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="A sample provenance record with this sample_id already exists",
        )

    soil_test_result = None
    if sample.soil_sample_id is not None:
        soil_test_result = await db.get(SoilTestResult, sample.soil_sample_id)
        if soil_test_result is None:
            raise HTTPException(status_code=404, detail=f"Soil sample {sample.soil_sample_id} was not found")
        if soil_test_result.sample_id != sample.sample_id:
            raise HTTPException(status_code=409, detail="sample_id must match the linked soil sample")
    else:
        soil_test_result = await db.scalar(
            select(SoilTestResult).where(SoilTestResult.sample_id == sample.sample_id)
        )

    if soil_test_result is not None:
        existing_link = await db.scalar(
            select(SampleProvenance.id).where(
                SampleProvenance.soil_sample_id == soil_test_result.id
            )
        )
        if existing_link is not None:
            raise HTTPException(status_code=409, detail="This soil test result already has a provenance record")

    db_sample = SampleProvenance(**sample.model_dump(exclude={"soil_sample_id"}))
    if soil_test_result is not None:
        db_sample.soil_sample_id = soil_test_result.id
        if (
            (soil_test_result.latitude is None or soil_test_result.longitude is None)
            and sample.latitude is not None
            and sample.longitude is not None
        ):
            soil_test_result.latitude = float(sample.latitude)
            soil_test_result.longitude = float(sample.longitude)
            soil_test_result.location = make_wgs84_point(
                soil_test_result.latitude,
                soil_test_result.longitude,
            )
    db.add(db_sample)
    await db.flush()

    result = await db.execute(
        select(SampleProvenance)
        .options(
            selectinload(SampleProvenance.owner),
            selectinload(SampleProvenance.collector),
        )
        .where(SampleProvenance.id == db_sample.id)
    )
    return result.scalar_one()


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
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> SoilSampleBatch:
    started_at = perf_counter()
    filename = (file.filename or "upload.csv").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    logger.info(
        "batch.upload.started",
        extra={"filename": filename, "upload_size_bytes": len(contents)},
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

    accepted_rows = 0 if row_errors else len(valid_samples)
    logger.info(
        "batch.validation.completed",
        extra={
            "filename": filename,
            "total_rows": total_rows,
            "accepted_rows": accepted_rows,
            "rejected_rows": total_rows - accepted_rows,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )
    batch = SoilSampleBatch(
        filename=filename,
        status="rejected" if row_errors else "completed",
        total_rows=total_rows,
        accepted_rows=accepted_rows,
        rejected_rows=total_rows - accepted_rows,
        errors=row_errors,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.flush()

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
        soil_rows: list[SoilTestResult] = []
        linked_rows: list[tuple[SampleProvenance, SoilTestResult]] = []
        for _, sample in valid_samples:
            provenance = provenance_by_sample_id.get(sample.sample_id)
            if provenance is not None and provenance.soil_sample_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Sample provenance {sample.sample_id} is already linked to a soil test record",
                )
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
            )
            soil_row = SoilTestResult(**sample_data)
            soil_rows.append(soil_row)
            if provenance is not None:
                linked_rows.append((provenance, soil_row))
        
        db.add_all(soil_rows)
        await db.flush()
        
        provenance_updates = {
            provenance.id: soil_row.id
            for provenance, soil_row in linked_rows
        }
        if provenance_updates:
            from sqlalchemy import update, case
            await db.execute(
                update(SampleProvenance)
                .where(SampleProvenance.id.in_(provenance_updates))
                .values(
                    soil_sample_id=case(
                        provenance_updates,
                        value=SampleProvenance.id,
                    )
                )
                .execution_options(synchronize_session=False)
            )

    try:
        batch.source_bucket, batch.source_key = await archive_batch_upload(
            contents=contents,
            object_key=f"soil-batches/{uuid.uuid4()}/{filename}",
        )
    except RuntimeError as exc:
        logger.exception("batch.archive.failed", extra={"batch_id": batch.id, "filename": filename})
        raise HTTPException(status_code=503, detail="Batch file storage is temporarily unavailable") from exc

    await db.refresh(batch)
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
    db: AsyncSession = Depends(get_db_session),
) -> SoilSampleBatch:
    batch = await db.get(SoilSampleBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Soil upload batch not found")
    return batch
