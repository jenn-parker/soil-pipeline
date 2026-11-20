from fastapi import Depends, HTTPException, Query, Request
from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import _accessible_sample_filter, _principal
from app.api.router import router
from app.database import get_db_session
from app.models.soil import SoilSampleAccess, SoilTestResult
from app.schemas.geojson import GeoJSONPoint, SoilSampleFeature, SoilSampleFeatureCollection, SoilSampleProperties

@router.get(
    "/maps/soil-samples",
    tags=["Mapping"],
    summary="Get soil sample locations as GeoJSON",
    description="Returns mapped soil samples within a longitude/latitude bounding box.",
    response_model=SoilSampleFeatureCollection,
)
async def get_soil_samples_geojson(
    request: Request,
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
            SoilTestResult.id,
            SoilTestResult.created_by_sub,
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
            _accessible_sample_filter(_principal(request)),
        )
        .order_by(SoilTestResult.sample_id)
        .limit(limit)
    )
    rows = result.all()
    principal = _principal(request)
    shared_roles: dict[int, str] = {}
    if principal.email and rows:
        shared = await db.execute(select(SoilSampleAccess.soil_sample_id, SoilSampleAccess.role).where(
            SoilSampleAccess.soil_sample_id.in_([row.id for row in rows]),
            func.lower(SoilSampleAccess.user_email) == principal.email,
        ))
        shared_roles = {sample_id: role for sample_id, role in shared.all()}
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
                can_edit=row.created_by_sub == principal.subject or shared_roles.get(row.id) == "editor",
                can_manage_access=row.created_by_sub == principal.subject,
            ),
        )
        for row in rows
    ]
    return SoilSampleFeatureCollection(features=features)




