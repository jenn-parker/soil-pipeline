from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.api import routes
from app.schemas.report import MeasurementRange, SoilRangeReport
from app.services.recommendations import (
    missing_recommendation_context,
    build_recommendation_guidance,
)
from app.schemas.recommendation import LocationRecommendationRequest
from app.schemas.soil import SoilTestResultCreate


def test_unit_explicit_soil_field_names_keep_legacy_api_keys() -> None:
    legacy_input = SoilTestResultCreate.model_validate(
        {
            "sample_id": "LEGACY-1",
            "cation_exchange_capacity": "12.50",
            "electrical_conductivity": "0.250",
        }
    )
    explicit_unit_input = SoilTestResultCreate.model_validate(
        {
            "sample_id": "NEW-1",
            "cation_exchange_capacity_meq_per_100g": "12.50",
            "electrical_conductivity_ds_m": "0.250",
        }
    )

    assert legacy_input.cation_exchange_capacity_meq_per_100g == Decimal("12.50")
    assert legacy_input.electrical_conductivity_ds_m == Decimal("0.250")
    assert explicit_unit_input.model_dump()["cation_exchange_capacity_meq_per_100g"] == Decimal("12.50")
    assert legacy_input.model_dump(by_alias=True)["cation_exchange_capacity"] == Decimal("12.50")
    assert legacy_input.model_dump(by_alias=True)["electrical_conductivity"] == Decimal("0.250")


def make_soil_summary(sample_count: int = 1) -> SoilRangeReport:
    sampled_at = datetime(2026, 10, 29, tzinfo=timezone.utc) if sample_count else None
    return SoilRangeReport(
        latitude=41.88,
        longitude=-93.10,
        radius_km=2,
        sample_count=sample_count,
        first_sampled_at=sampled_at,
        last_sampled_at=sampled_at,
        measurements=(
            {
                "soil_ph": MeasurementRange(
                    sample_count=sample_count,
                    minimum=Decimal("5.8"),
                    maximum=Decimal("6.1"),
                )
            }
            if sample_count
            else {}
        ),
    )


def test_recommendation_request_validates_geographic_bounds() -> None:
    valid = LocationRecommendationRequest(
        latitude=41.88,
        longitude=-93.10,
        radius_km=2,
    )
    assert valid.latitude == 41.88

    with pytest.raises(ValueError):
        LocationRecommendationRequest(
            latitude=91,
            longitude=-93.10,
            radius_km=2,
        )

    with pytest.raises(ValueError):
        LocationRecommendationRequest(
            latitude=41.88,
            longitude=-93.10,
            radius_km=0,
        )


def test_missing_context_requires_yield_goal_unit() -> None:
    request = LocationRecommendationRequest(
        latitude=41.88,
        longitude=-93.10,
        radius_km=2,
        crop="corn",
        state_province="Iowa",
        yield_goal=180,
        soil_test_lab="Lab A",
        soil_test_method="Mehlich-3",
    )

    assert missing_recommendation_context(request) == ["yield_goal_unit"]


@pytest.mark.parametrize(
    ("sample_count", "missing_context", "expected_status"),
    [
        (0, [], "no_local_samples"),
        (2, ["crop"], "context_required"),
        (2, [], "calibration_not_configured"),
    ],
)
def test_recommendation_statuses(
    sample_count: int,
    missing_context: list[str],
    expected_status: str,
) -> None:
    status, guidance = build_recommendation_guidance(
        make_soil_summary(sample_count),
        missing_context,
    )

    assert status == expected_status
    assert guidance


def test_location_recommendation_endpoint_returns_summary(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes,
        "get_soil_range_report",
        AsyncMock(return_value=make_soil_summary()),
    )

    response = client.post(
        "/api/v1/recommendations/location",
        json={
            "latitude": 41.88,
            "longitude": -93.10,
            "radius_km": 2,
            "crop": "corn",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "context_required"
    assert body["soil_summary"]["sample_count"] == 1
    assert "state_province" in body["missing_context"]
    assert body["ai_assisted"] is False


def test_location_recommendation_does_not_call_ai_when_not_requested(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes,
        "get_soil_range_report",
        AsyncMock(return_value=make_soil_summary()),
    )
    ai_explainer = AsyncMock()
    monkeypatch.setattr(routes, "explain_soil_summary", ai_explainer)

    response = client.post(
        "/api/v1/recommendations/location",
        json={
            "latitude": 41.88,
            "longitude": -93.10,
            "radius_km": 2,
            "include_ai_explanation": False,
        },
    )

    assert response.status_code == 200
    ai_explainer.assert_not_awaited()


def test_location_recommendation_skips_ai_when_no_samples(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes,
        "get_soil_range_report",
        AsyncMock(return_value=make_soil_summary(sample_count=0)),
    )
    ai_explainer = AsyncMock()
    monkeypatch.setattr(routes, "explain_soil_summary", ai_explainer)

    response = client.post(
        "/api/v1/recommendations/location",
        json={
            "latitude": 41.88,
            "longitude": -93.10,
            "radius_km": 2,
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "no_local_samples"
    ai_explainer.assert_not_awaited()


def test_location_recommendation_uses_mock_ai_mode_without_openai(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_EXPLANATION_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        routes,
        "get_soil_range_report",
        AsyncMock(return_value=make_soil_summary()),
    )

    response = client.post(
        "/api/v1/recommendations/location",
        json={
            "latitude": 41.88,
            "longitude": -93.10,
            "radius_km": 2,
            "crop": "corn",
            "state_province": "Iowa",
            "yield_goal": 200,
            "yield_goal_unit": "bu/acre",
            "soil_test_lab": "Example Lab",
            "soil_test_method": "Mehlich-3",
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "calibration_not_configured"
    assert body["missing_context"] == []
    assert body["ai_assisted"] is True
    assert body["ai_explanation"].startswith("Demo AI explanation:")
    assert "corn, Iowa, 200 bu/acre" in body["ai_explanation"]


def test_location_recommendation_validates_input(client) -> None:
    response = client.post(
        "/api/v1/recommendations/location",
        json={"latitude": 100, "longitude": 0, "radius_km": 2},
    )

    assert response.status_code == 422
