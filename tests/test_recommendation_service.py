import asyncio

import pytest

from app.schemas.recommendation import LocationRecommendationRequest
from app.schemas.report import MeasurementRange, SoilRangeReport
from app.services import recommendations


def summary(count: int) -> SoilRangeReport:
    return SoilRangeReport(
        latitude=42,
        longitude=-93,
        radius_km=10,
        sample_count=count,
        first_sampled_at=None,
        last_sampled_at=None,
        measurements={
            "soil_ph": MeasurementRange(sample_count=count, minimum=6, maximum=7),
        } if count else {},
    )


def test_missing_context_and_guidance_cover_complete_context() -> None:
    complete = LocationRecommendationRequest(
        latitude=42,
        longitude=-93,
        radius_km=10,
        crop="corn",
        state_province="Iowa",
        yield_goal=180,
        yield_goal_unit="bu/ac",
        soil_test_lab="Lab",
        soil_test_method="Mehlich-3",
    )
    assert recommendations.missing_recommendation_context(complete) == []
    status, guidance = recommendations.build_recommendation_guidance(summary(2), [])
    assert status == "calibration_not_configured"
    assert guidance[-1].startswith("Required caller context")


def test_ai_explanation_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = LocationRecommendationRequest(latitude=42, longitude=-93, radius_km=10)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        asyncio.run(recommendations.explain_soil_summary(request, summary(1), ["crop"]))


def test_mock_ai_explanation_does_not_require_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_EXPLANATION_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = LocationRecommendationRequest(
        latitude=42,
        longitude=-93,
        radius_km=10,
        crop="corn",
        state_province="Iowa",
        yield_goal=200,
        yield_goal_unit="bu/acre",
    )

    explanation = asyncio.run(recommendations.explain_soil_summary(request, summary(2), ["crop"]))

    assert explanation.startswith("Demo AI explanation:")
    assert "2 nearby samples" in explanation
    assert "corn, Iowa, 200 bu/acre" in explanation
