from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.soil import SoilTestResult

# ==========================================
# 1. SQLALCHEMY ORM MODELS
# ==========================================

class Party(Base):
    __tablename__ = "parties"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Relationships
    owned_sample_provenance: Mapped[list["SampleProvenance"]] = relationship(
        "SampleProvenance",
        foreign_keys="SampleProvenance.owner_id",
        back_populates="owner",
    )
    collected_sample_provenance: Mapped[list["SampleProvenance"]] = relationship(
        "SampleProvenance",
        foreign_keys="SampleProvenance.collector_id",
        back_populates="collector",
    )


class SampleProvenance(Base):
    __tablename__ = "sample_identifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soil_sample_id: Mapped[int | None] = mapped_column(
        ForeignKey("soil_samples.id"), nullable=True, unique=True, index=True
    )
    sample_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # Lab barcode or custom ID
    alternate_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Field-side tag or grower tracking code
    
    # Temporal Metadata
    collection_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    collection_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Parties / Personnel
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey('parties.id'), nullable=False)
    collector_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('parties.id'), nullable=True)  # Person who physically pulled the core
    
    # Geographic & Field Provenance
    farm_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    management_zone: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Grid ID or Management Zone Name
    
    # Address / Legal Cadastre Data
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, default="USA")
    legal_description: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Township/Range/Section or APN/Parcel ID
    
    # Geospatial Core (Using Decimal for high precision coordinate storage)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    elevation_meters: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    gps_accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    
    # Collection Protocol Metadata
    sampling_depth_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True, comment="Target depth of the core profile")
    cores_per_composite: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Number of physical cores blended into this sample")
    sampling_method: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="Grid, Zone, Composite, Topographic, etc.")
    previous_crop: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    owner: Mapped[Party] = relationship(
        "Party", foreign_keys=[owner_id], back_populates="owned_sample_provenance"
    )
    collector: Mapped[Party | None] = relationship(
        "Party", foreign_keys=[collector_id], back_populates="collected_sample_provenance"
    )
    soil_test_result: Mapped["SoilTestResult | None"] = relationship(
        back_populates="provenance"
    )
