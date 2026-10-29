import json
import os

from pydantic import BaseModel

from app.schemas.recommendation import LocationRecommendationRequest
from app.schemas.report import SoilRangeReport


class SoilSummaryExplanation(BaseModel):
    summary: str


def missing_recommendation_context(
    request: LocationRecommendationRequest,
) -> list[str]:
    required_context = {
        "crop": request.crop,
        "state_province": request.state_province,
        "yield_goal": request.yield_goal,
        "soil_test_lab": request.soil_test_lab,
        "soil_test_method": request.soil_test_method,
    }
    missing = [name for name, value in required_context.items() if value is None or value == ""]
    if request.yield_goal is not None and not request.yield_goal_unit:
        missing.append("yield_goal_unit")
    return missing


def build_recommendation_guidance(
    soil_summary: SoilRangeReport,
    missing_context: list[str],
) -> tuple[str, list[str]]:
    if soil_summary.sample_count == 0:
        return "no_local_samples", [
            "No geolocated soil samples were found within the requested radius.",
            "Add a current soil test with coordinates before drawing location-specific conclusions.",
            "No crop or nutrient recommendations can be made from an empty sample set.",
        ]

    guidance = [
        "The values summarize multiple nearby samples; their ranges do not describe one composite sample.",
        "This first pass does not calculate crop suitability, fertilizer products, or application rates.",
        "Use crop-, region-, and soil-test-method-specific extension guidance before making nutrient decisions.",
    ]
    if missing_context:
        guidance.append("Provide the missing crop, region, yield, and laboratory context for a later calibrated recommendation step.")
        return "context_required", guidance

    guidance.append("Required caller context is present, but a validated regional recommendation rule set is not configured yet.")
    return "calibration_not_configured", guidance


async def explain_soil_summary(
    request: LocationRecommendationRequest,
    soil_summary: SoilRangeReport,
    missing_context: list[str],
) -> str:
    try:
        from openai import AsyncOpenAI, OpenAIError
    except ImportError as exc:
        raise RuntimeError("AI explanations require installing the openai package") from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("AI explanations require OPENAI_API_KEY")

    # Keep exact coordinates, sample IDs, names, and other identifiers out of the model request.
    context = {
        "crop": request.crop,
        "state_or_region": request.state_province,
        "yield_goal": str(request.yield_goal) if request.yield_goal is not None else None,
        "yield_goal_unit": request.yield_goal_unit,
        "soil_test_lab": request.soil_test_lab,
        "soil_test_method": request.soil_test_method,
        "previous_crop": request.previous_crop,
        "irrigation": request.irrigation,
        "tillage": request.tillage,
        "sample_count": soil_summary.sample_count,
        "first_sampled_at": soil_summary.first_sampled_at.isoformat() if soil_summary.first_sampled_at else None,
        "last_sampled_at": soil_summary.last_sampled_at.isoformat() if soil_summary.last_sampled_at else None,
        "measurement_ranges": soil_summary.model_dump(mode="json")["measurements"],
        "missing_context": missing_context,
    }

    instructions = (
        "Explain the supplied soil-test summary in plain language. The ranges combine nearby samples and "
        "may reflect different fields; do not treat them as one sample. You are not an agronomic decision "
        "engine. Do not recommend crops, diagnose deficiencies, name products, or give fertilizer, lime, "
        "or pesticide rates. Do not invent thresholds, measurements, weather, or sources. State that the "
        "summary is not sufficient for application decisions and point out the listed missing context. "
        "Return one concise paragraph only."
    )

    try:
        async with AsyncOpenAI(api_key=api_key, timeout=15.0, max_retries=1) as client:
            response = await client.responses.parse(
                model=os.getenv("OPENAI_MODEL", "gpt-6-astra"),
                input=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(context)},
                ],
                text_format=SoilSummaryExplanation,
            )
    except OpenAIError as exc:
        raise RuntimeError("AI explanation service is unavailable") from exc

    parsed = response.output_parsed
    if parsed is None or not parsed.summary.strip() or len(parsed.summary) > 1200:
        raise RuntimeError("AI explanation service returned no usable explanation")
    return parsed.summary
