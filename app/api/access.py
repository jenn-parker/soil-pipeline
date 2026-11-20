from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import _get_owned_sample, _principal
from app.api.router import router
from app.auth import require_scope
from app.database import get_db_session
from app.models.soil import SoilSampleAccess
from app.schemas.access import SampleAccessGrant, SampleAccessRead

@router.get(
    "/soil-samples/{sample_id}/access",
    tags=["Soil samples"],
    summary="List users with access to an owned soil sample",
    response_model=list[SampleAccessRead],
)
async def list_sample_access(
    request: Request,
    sample_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> list[SampleAccessRead]:
    db_sample = await _get_owned_sample(sample_id, _principal(request), db)
    records = (await db.scalars(select(SoilSampleAccess).where(SoilSampleAccess.soil_sample_id == db_sample.id).order_by(SoilSampleAccess.user_email))).all()
    return [SampleAccessRead(email=record.user_email, role=record.role, granted_at=record.created_at) for record in records]


@router.post(
    "/soil-samples/{sample_id}/access",
    tags=["Soil samples"],
    summary="Grant a user access to an owned soil sample",
    response_model=SampleAccessRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def grant_sample_access(
    request: Request,
    sample_id: str,
    grant: SampleAccessGrant,
    db: AsyncSession = Depends(get_db_session),
) -> SampleAccessRead:
    principal = _principal(request)
    db_sample = await _get_owned_sample(sample_id, principal, db)
    email = str(grant.email).strip().lower()
    if principal.email == email:
        raise HTTPException(status_code=400, detail="The owner already has access")
    record = await db.scalar(select(SoilSampleAccess).where(
        SoilSampleAccess.soil_sample_id == db_sample.id,
        func.lower(SoilSampleAccess.user_email) == email,
    ))
    if record is None:
        record = SoilSampleAccess(soil_sample_id=db_sample.id, user_email=email, role=grant.role, granted_by_sub=principal.subject)
        db.add(record)
    else:
        record.role = grant.role
        record.granted_by_sub = principal.subject
    await db.flush()
    await db.refresh(record)
    return SampleAccessRead(email=record.user_email, role=record.role, granted_at=record.created_at)


@router.delete(
    "/soil-samples/{sample_id}/access/{email}",
    tags=["Soil samples"],
    summary="Revoke a user's access to an owned soil sample",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_scope("soil:write"))],
)
async def revoke_sample_access(
    request: Request,
    sample_id: str,
    email: str,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    db_sample = await _get_owned_sample(sample_id, _principal(request), db)
    record = await db.scalar(select(SoilSampleAccess).where(
        SoilSampleAccess.soil_sample_id == db_sample.id,
        func.lower(SoilSampleAccess.user_email) == email.strip().lower(),
    ))
    if record is not None:
        await db.delete(record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



