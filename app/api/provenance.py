from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import make_wgs84_point
from app.api.router import router
from app.auth import require_scope
from app.database import get_db_session
from app.models.sample import Party, SampleProvenance
from app.models.soil import SoilTestResult
from app.schemas.sample import PartyCreate, PartyRead, SampleProvenanceCreate, SampleProvenanceRead

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



