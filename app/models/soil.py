from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement, WKTElement
from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.sample import SampleProvenance

from app.database import Base

class SoilTestResult(Base):
    __tablename__ = "soil_samples"

    # Metadata & Geography
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("soil_upload_batches.id"), nullable=True, index=True)
    created_by_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archived_by_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[WKBElement | WKTElement | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    sample_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    sampling_depth_inches: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Chemical Baseline
    soil_ph: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    buffer_ph: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    organic_matter_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    cation_exchange_capacity_meq_per_100g: Mapped[Decimal | None] = mapped_column(
        "cation_exchange_capacity", Numeric(5, 2), nullable=True
    )
    electrical_conductivity_ds_m: Mapped[Decimal | None] = mapped_column(
        "electrical_conductivity", Numeric(6, 3), nullable=True
    )

    # Macronutrients
    nitrate_nitrogen_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    phosphorus_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    phosphorus_extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    potassium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Secondary Nutrients
    sulfur_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    calcium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    magnesium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    sodium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Micronutrients
    zinc_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    iron_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    manganese_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    copper_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    boron_ppm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Physical Properties
    sand_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    silt_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    clay_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    bulk_density_g_cm3: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)

    # Base Saturations (%)
    calcium_saturation_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    magnesium_saturation_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    potassium_saturation_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    hydrogen_saturation_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sodium_saturation_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    provenance: Mapped["SampleProvenance | None"] = relationship(
        back_populates="soil_test_result", uselist=False
    )


class SoilSampleAccess(Base):
    __tablename__ = "soil_sample_access"
    __table_args__ = (
        UniqueConstraint(
            "soil_sample_id",
            "user_email",
            name="uq_soil_sample_access_sample_email",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soil_sample_id: Mapped[int] = mapped_column(ForeignKey("soil_samples.id", ondelete="CASCADE"), nullable=False, index=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    granted_by_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
