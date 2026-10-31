import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app import api
from app.api import routes
from app.auth import Principal


def request_with_email() -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            principal=Principal(subject="viewer-sub", scopes=frozenset(), email="viewer@example.com")
        )
    )


def test_report_builds_measurement_ranges() -> None:
    row = {
        "sample_count": 2,
        "first_sampled_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "last_sampled_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
    }
    for name in routes.SOIL_MEASUREMENTS:
        row[f"{name}_count"] = 1 if name == "soil_ph" else 0
        row[f"{name}_minimum"] = 6 if name == "soil_ph" else None
        row[f"{name}_maximum"] = 7 if name == "soil_ph" else None

    result = SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))
    db = MagicMock(execute=AsyncMock(return_value=result))
    report = asyncio.run(
        routes.get_soil_range_report(
            request_with_email(), latitude=42, longitude=-93, radius_km=10, db=db
        )
    )

    assert report.sample_count == 2
    assert report.measurements["soil_ph"].minimum == 6
    assert "sand_pct" not in report.measurements


def test_map_serializes_owner_and_shared_editor_permissions() -> None:
    row = SimpleNamespace(
        id=7,
        created_by_sub="other-sub",
        sample_id="FIELD-7",
        field_name="North Field",
        sampled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        soil_ph=6.5,
        organic_matter_pct=3,
        sand_pct=None,
        silt_pct=None,
        clay_pct=None,
        longitude=-92.4,
        latitude=42.7,
    )
    map_result = SimpleNamespace(all=lambda: [row])
    access_result = SimpleNamespace(all=lambda: [(7, "editor")])
    db = MagicMock(execute=AsyncMock(side_effect=[map_result, access_result]))

    feature_collection = asyncio.run(
        routes.get_soil_samples_geojson(
            request_with_email(), west=-97, south=40, east=-89, north=44, limit=1000, db=db
        )
    )

    feature = feature_collection.features[0]
    assert feature.geometry.coordinates == (-92.4, 42.7)
    assert feature.properties.can_edit is True
    assert feature.properties.can_manage_access is False
