from fastapi import Depends, HTTPException, Query, Request
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import _accessible_sample_filter, _principal, make_wgs84_point
from app.api.router import router
from app.database import get_db_session
from app.models.soil import SoilTestResult
from app.schemas.recommendation import LocationRecommendationRequest, LocationRecommendationResponse
from app.schemas.report import MeasurementRange, SoilRangeReport
from app.services.recommendations import build_recommendation_guidance, explain_soil_summary, missing_recommendation_context

SOIL_MEASUREMENTS = (
    "soil_ph", "buffer_ph", "organic_matter_pct", "cation_exchange_capacity",
    "electrical_conductivity", "nitrate_nitrogen_ppm", "phosphorus_ppm",
    "potassium_ppm", "sulfur_ppm", "calcium_ppm", "magnesium_ppm", "sodium_ppm",
    "zinc_ppm", "iron_ppm", "manganese_ppm", "copper_ppm", "boron_ppm",
    "sand_pct", "silt_pct", "clay_pct", "bulk_density_g_cm3",
    "calcium_saturation_pct", "magnesium_saturation_pct",
    "potassium_saturation_pct", "hydrogen_saturation_pct", "sodium_saturation_pct",
)
SOIL_MEASUREMENT_ATTRIBUTES = {
    "cation_exchange_capacity": "cation_exchange_capacity_meq_per_100g",
    "electrical_conductivity": "electrical_conductivity_ds_m",
}

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
    request: Request,
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

    filters = [
        SoilTestResult.location.is_not(None),
        func.ST_DWithin(SoilTestResult.location, center_point, radius_km * 1000),
    ]
    if request is not None:
        filters.append(_accessible_sample_filter(_principal(request)))
    result = await db.execute(
        select(*aggregates)
        .where(*filters)
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
    request: Request,
    recommendation_request: LocationRecommendationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> LocationRecommendationResponse:
    soil_summary = await get_soil_range_report(
        request,
        recommendation_request.latitude,
        recommendation_request.longitude,
        recommendation_request.radius_km,
        db,
    )
    missing_context = missing_recommendation_context(recommendation_request)
    recommendation_status, guidance = build_recommendation_guidance(soil_summary, missing_context)

    ai_explanation = None
    if recommendation_request.include_ai_explanation and soil_summary.sample_count > 0:
        try:
            ai_explanation = await explain_soil_summary(recommendation_request, soil_summary, missing_context)
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



