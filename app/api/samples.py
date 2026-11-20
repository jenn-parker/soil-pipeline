from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import _accessible_sample_filter, _get_editable_sample, _get_owned_sample, _principal, make_wgs84_point
from app.api.router import router
from app.auth import require_scope
from app.database import get_db_session
from app.models.sample import SampleProvenance
from app.models.soil import SoilTestResult
from app.schemas.soil import SoilTestResultCreate, SoilTestResultRead

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
    request: Request,
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
        created_by_sub=_principal(request).subject,
    )
    db_sample = SoilTestResult(**sample_data)
    db.add(db_sample)
    await db.flush()
    if provenance is not None:
        provenance.soil_sample_id = db_sample.id
    await db.refresh(db_sample)
    return db_sample


@router.get(
    "/soil-samples/mine",
    tags=["Soil samples"],
    summary="List the current user's soil samples",
    response_model=list[SoilTestResultRead],
)
async def list_owned_soil_samples(
    include_archived: bool = Query(False),
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
) -> list[SoilTestResult]:
    filters = [SoilTestResult.created_by_sub == _principal(request).subject]
    if not include_archived:
        filters.append(SoilTestResult.archived_at.is_(None))
    result = await db.scalars(
        select(SoilTestResult).where(*filters).order_by(SoilTestResult.sampled_at.desc(), SoilTestResult.sample_id)
    )
    return list(result.all())


@router.get(
    "/soil-samples/{sample_id}",
    tags=["Soil samples"],
    summary="Read one accessible soil test record",
    response_model=SoilTestResultRead,
)
async def get_soil_test_result(
    sample_id: str,
    db: AsyncSession = Depends(get_db_session),
    request: Request = None,
) -> SoilTestResult:
    sample = await db.scalar(select(SoilTestResult).where(
        SoilTestResult.sample_id == sample_id,
        _accessible_sample_filter(_principal(request)),
    ))
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Soil sample {sample_id} was not found")
    return sample


@router.put(
    "/soil-samples/{sample_id}",
    tags=["Soil samples"],
    summary="Update an owned or shared soil test record",
    response_model=SoilTestResultRead,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def update_soil_test_result(
    request: Request,
    sample_id: str,
    sample: SoilTestResultCreate,
    db: AsyncSession = Depends(get_db_session),
) -> SoilTestResult:
    if sample.sample_id != sample_id:
        raise HTTPException(status_code=400, detail="The path sample_id must match the request body")
    db_sample = await _get_editable_sample(sample_id, _principal(request), db)
    sample_data = sample.model_dump()
    sample_data.update(
        latitude=sample.latitude,
        longitude=sample.longitude,
        location=make_wgs84_point(sample.latitude, sample.longitude),
    )
    for field, value in sample_data.items():
        if field not in {"sample_id", "created_by_sub"}:
            setattr(db_sample, field, value)
    await db.flush()
    await db.refresh(db_sample)
    return db_sample


@router.delete(
    "/soil-samples/{sample_id}",
    tags=["Soil samples"],
    summary="Delete an owned soil test record",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def delete_soil_test_result(
    request: Request,
    sample_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    db_sample = await _get_owned_sample(sample_id, _principal(request), db)
    await db.delete(db_sample)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/soil-samples/{sample_id}/archive",
    tags=["Soil samples"],
    summary="Archive an owned soil test record",
    response_model=SoilTestResultRead,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def archive_soil_test_result(
    request: Request,
    sample_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> SoilTestResult:
    principal = _principal(request)
    sample = await _get_owned_sample(sample_id, principal, db)
    if sample.archived_at is None:
        sample.archived_at = datetime.now(timezone.utc)
        sample.archived_by_sub = principal.subject
        await db.flush()
    await db.refresh(sample)
    return sample


@router.post(
    "/soil-samples/{sample_id}/restore",
    tags=["Soil samples"],
    summary="Restore an owned archived soil test record",
    response_model=SoilTestResultRead,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def restore_soil_test_result(
    request: Request,
    sample_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> SoilTestResult:
    sample = await _get_owned_sample(sample_id, _principal(request), db)
    sample.archived_at = None
    sample.archived_by_sub = None
    await db.flush()
    await db.refresh(sample)
    return sample



