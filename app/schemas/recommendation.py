from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.report import SoilRangeReport


class LocationRecommendationRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(..., gt=0, le=1000)
    crop: str | None = Field(None, max_length=100)
    state_province: str | None = Field(None, max_length=100)
    yield_goal: Decimal | None = Field(None, gt=0)
    yield_goal_unit: str | None = Field(None, max_length=40)
    soil_test_lab: str | None = Field(None, max_length=150)
    soil_test_method: str | None = Field(None, max_length=100)
    previous_crop: str | None = Field(None, max_length=100)
    irrigation: str | None = Field(None, max_length=50)
    tillage: str | None = Field(None, max_length=50)
    include_ai_explanation: bool = False

    model_config = ConfigDict(extra="forbid")


class LocationRecommendationResponse(BaseModel):
    status: Literal["no_local_samples", "context_required", "calibration_not_configured"]
    soil_summary: SoilRangeReport
    missing_context: list[str]
    guidance: list[str]
    ai_assisted: bool
    ai_explanation: str | None = None
