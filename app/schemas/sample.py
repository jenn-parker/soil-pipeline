from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field



class PartyBase(BaseModel):
    name: str = Field(..., max_length=255, description="Full name of the individual or entity")
    organization: str | None = Field(None, max_length=255, description="Company, agency, or farm operation name")
    email: EmailStr | None = Field(None, description="Contact electronic mail address")
    phone: str | None = Field(None, max_length=50, description="Contact telephone number")

class PartyCreate(PartyBase):
    pass

class PartyRead(PartyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SampleProvenanceBase(BaseModel):
    sample_id: str = Field(..., max_length=100, description="Primary unique string token tracking this physical sample")
    alternate_id: str | None = Field(None, max_length=100, description="Secondary grower code or bag reference number")
    
    collection_date: date = Field(..., description="The calendar day the soil core was extracted")
    collection_time: datetime | None = Field(None, description="Optional time stamp of physical extraction")
    received_date: date | None = Field(None, description="The day the facility logged the sample package")
    
    farm_name: str | None = Field(None, max_length=255, description="Name of the overarching farming unit")
    field_name: str | None = Field(None, max_length=255, description="Specific named sub-unit boundary or lot")
    management_zone: str | None = Field(None, max_length=100, description="Sub-field grid block, zone identifier, or soil type delineation")
    
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state_province: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str = Field("USA", max_length=100)
    legal_description: str | None = Field(None, max_length=255, description="Section-Township-Range coordinates or Assessor Parcel Number")
    
    latitude: Decimal | None = Field(None, ge=-90, le=90, max_digits=9, decimal_places=6, description="WGS84 Latitude reference decimal coordinate")
    longitude: Decimal | None = Field(None, ge=-180, le=180, max_digits=9, decimal_places=6, description="WGS84 Longitude reference decimal coordinate")
    elevation_meters: Decimal | None = Field(None, ge=-400, le=9000, max_digits=6, decimal_places=2)
    gps_accuracy_meters: Decimal | None = Field(None, ge=0, max_digits=4, decimal_places=2)
    
    sampling_depth_cm: Decimal | None = Field(None, ge=0, max_digits=5, decimal_places=2, description="Physical extraction length down the soil profile")
    cores_per_composite: int | None = Field(None, ge=1, description="Count of separate structural slices mixed together")
    sampling_method: str | None = Field(None, max_length=100, description="Pattern used to survey layout e.g. 2.5ac grid")
    previous_crop: str | None = Field(None, max_length=100, description="Vegetation background info to help compute target N-P-K recommendation offsets")
    notes: str | None = Field(None, max_length=1000)

class SampleProvenanceCreate(SampleProvenanceBase):
    owner_id: int
    collector_id: int | None = None
    soil_sample_id: int | None = None

class SampleProvenanceRead(SampleProvenanceBase):
    id: int
    owner_id: int
    collector_id: int | None = None
    soil_sample_id: int | None = None
    owner: PartyRead
    collector: PartyRead | None = None

    model_config = ConfigDict(from_attributes=True)
