from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MeasurementRange(BaseModel):
    sample_count: int
    minimum: Decimal | None
    maximum: Decimal | None


class SoilRangeReport(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    sample_count: int
    first_sampled_at: datetime | None
    last_sampled_at: datetime | None
    measurements: dict[str, MeasurementRange]
