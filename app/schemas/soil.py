from datetime import datetime, timezone
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field



class SoilTestResultBase(BaseModel):
    # Metadata & Geography
    sample_id: str = Field(..., min_length=1, max_length=50, description="Unique identifier from the lab or client")
    field_name: str | None = Field(None, max_length=100, description="Name or identifier of the field sampled")
    sampled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp associated with this soil test record; defaults to record creation time.",
    )
    sampling_depth_inches: Decimal | None = Field(None, max_digits=5, decimal_places=2)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    # Chemical Baseline
    soil_ph: Decimal | None = Field(None, ge=0, le=14, max_digits=4, decimal_places=2)
    buffer_ph: Decimal | None = Field(None, ge=0, le=14, max_digits=4, decimal_places=2)
    organic_matter_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    cation_exchange_capacity_meq_per_100g: Decimal | None = Field(
        None,
        ge=0,
        max_digits=5,
        decimal_places=2,
        validation_alias=AliasChoices(
            "cation_exchange_capacity_meq_per_100g", "cation_exchange_capacity"
        ),
        serialization_alias="cation_exchange_capacity",
        description="Cation exchange capacity in milliequivalents per 100 grams (meq/100 g).",
    )
    electrical_conductivity_ds_m: Decimal | None = Field(
        None,
        ge=0,
        max_digits=6,
        decimal_places=3,
        validation_alias=AliasChoices(
            "electrical_conductivity_ds_m", "electrical_conductivity"
        ),
        serialization_alias="electrical_conductivity",
        description="Electrical conductivity in decisiemens per meter (dS/m).",
    )

    # Macronutrients
    nitrate_nitrogen_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    phosphorus_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    phosphorus_extraction_method: str | None = Field(None, max_length=50, description="e.g., Bray-1, Mehlich-3, Olsen")
    potassium_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)

    # Secondary Nutrients
    sulfur_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    calcium_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    magnesium_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    sodium_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)

    # Micronutrients
    zinc_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    iron_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    manganese_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    copper_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)
    boron_ppm: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=2)

    # Physical Properties
    sand_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    silt_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    clay_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    bulk_density_g_cm3: Decimal | None = Field(None, ge=0, max_digits=4, decimal_places=2)

    # Base Saturations (%)
    calcium_saturation_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    magnesium_saturation_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    potassium_saturation_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    hydrogen_saturation_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    sodium_saturation_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)

    model_config = ConfigDict(from_attributes=True)

class SoilTestResultCreate(SoilTestResultBase):
    pass

class SoilTestResultRead(SoilTestResultBase):
    id: int
