from pydantic import ValidationError
import pytest

from app.models.batch import SoilSampleBatch
from app.models.soil import SoilTestResult
from app.schemas.sample import SampleProvenanceCreate
from app.schemas.soil import SoilTestResultCreate
from app.services.batch_state import transition_archive_status, transition_batch_status


def constraint_names(model: type[object]) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name is not None
    }


def test_coordinates_must_be_provided_as_a_pair() -> None:
    with pytest.raises(ValidationError, match="provided together"):
        SoilTestResultCreate(sample_id="PARTIAL-COORDS", latitude=42.7)

    with pytest.raises(ValidationError, match="provided together"):
        SoilTestResultCreate(sample_id="PARTIAL-COORDS", longitude=-92.4)


def test_database_models_declare_core_invariant_constraints() -> None:
    assert {
        "ck_soil_samples_latitude_range",
        "ck_soil_samples_longitude_range",
        "ck_soil_samples_coordinate_pair",
        "ck_soil_samples_soil_ph_range",
    } <= constraint_names(SoilTestResult)
    assert {
        "ck_soil_upload_batches_status",
        "ck_soil_upload_batches_archive_status",
        "ck_soil_upload_batches_row_counts",
    } <= constraint_names(SoilSampleBatch)


def test_provenance_coordinates_and_dates_are_consistent() -> None:
    with pytest.raises(ValidationError, match="provided together"):
        SampleProvenanceCreate(
            sample_id="PROV-1",
            collection_date="2026-01-02",
            owner_id=1,
            latitude=42.7,
        )

    with pytest.raises(ValidationError, match="before collection_date"):
        SampleProvenanceCreate(
            sample_id="PROV-1",
            collection_date="2026-01-02",
            received_date="2026-01-01",
            owner_id=1,
        )


def test_batch_state_transitions_reject_illegal_changes() -> None:
    batch = SoilSampleBatch(status="processing", archive_status="pending")
    transition_batch_status(batch, "completed")
    transition_archive_status(batch, "archived")
    assert batch.status == "completed"
    assert batch.archive_status == "archived"

    with pytest.raises(ValueError, match="Illegal batch status transition"):
        transition_batch_status(batch, "failed")
    with pytest.raises(ValueError, match="Illegal archive status transition"):
        transition_archive_status(batch, "abandoned")
