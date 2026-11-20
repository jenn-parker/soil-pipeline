from fastapi import HTTPException, Request
from geoalchemy2.elements import WKTElement
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal
from app.models.soil import SoilSampleAccess, SoilTestResult


def make_wgs84_point(latitude: float | None, longitude: float | None) -> WKTElement | None:
    if latitude is None or longitude is None:
        return None
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def _principal(request: Request) -> Principal:
    return request.state.principal


def _accessible_sample_filter(principal: Principal):
    shared = false()
    if principal.email:
        shared = select(SoilSampleAccess.id).where(
            SoilSampleAccess.soil_sample_id == SoilTestResult.id,
            func.lower(SoilSampleAccess.user_email) == principal.email,
        ).exists()
    return and_(
        SoilTestResult.archived_at.is_(None),
        or_(
            SoilTestResult.created_by_sub.is_(None),
            SoilTestResult.created_by_sub == principal.subject,
            shared,
        ),
    )


async def _get_owned_sample(sample_id: str, principal: Principal, db: AsyncSession) -> SoilTestResult:
    sample = await db.scalar(select(SoilTestResult).where(SoilTestResult.sample_id == sample_id))
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Soil sample {sample_id} was not found")
    if sample.created_by_sub != principal.subject:
        raise HTTPException(status_code=403, detail="Only the sample owner can manage sharing")
    return sample


async def _get_editable_sample(sample_id: str, principal: Principal, db: AsyncSession) -> SoilTestResult:
    sample = await db.scalar(select(SoilTestResult).where(SoilTestResult.sample_id == sample_id))
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Soil sample {sample_id} was not found")
    if sample.archived_at is not None:
        raise HTTPException(status_code=409, detail="This sample is archived; restore it before editing")
    if sample.created_by_sub == principal.subject:
        return sample
    if principal.email:
        can_edit = await db.scalar(select(SoilSampleAccess.id).where(
            SoilSampleAccess.soil_sample_id == sample.id,
            func.lower(SoilSampleAccess.user_email) == principal.email,
            SoilSampleAccess.role == "editor",
        ))
        if can_edit:
            return sample
    raise HTTPException(status_code=403, detail="You do not have edit access to this sample")

