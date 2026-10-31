from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class GeoJSONPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class SoilSampleProperties(BaseModel):
    sample_id: str
    field_name: str | None
    sampled_at: datetime
    soil_ph: Decimal | None
    organic_matter_pct: Decimal | None
    sand_pct: Decimal | None
    silt_pct: Decimal | None
    clay_pct: Decimal | None
    can_edit: bool = False
    can_manage_access: bool = False


class SoilSampleFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPoint
    properties: SoilSampleProperties


class SoilSampleFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SoilSampleFeature]
