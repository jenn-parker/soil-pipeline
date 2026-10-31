from app.migration_config import include_name, include_object


def test_alembic_limits_reflection_to_application_schema() -> None:
    assert include_name("public", "schema", {}) is True
    assert include_name(None, "schema", {}) is True
    assert include_name("tiger", "schema", {}) is False
    assert include_name("topology", "table", {"schema_name": "topology"}) is False


def test_alembic_includes_application_objects() -> None:
    assert include_object(object(), "soil_samples", "table", True, None) is True
    assert include_object(object(), "soil_samples", "column", True, None) is True


def test_alembic_excludes_reflected_postgis_catalog_table() -> None:
    assert include_object(object(), "spatial_ref_sys", "table", True, None) is False
    assert include_object(object(), "spatial_ref_sys", "table", False, None) is False


def test_alembic_excludes_reflected_postgis_catalog_views() -> None:
    for relation in ("geography_columns", "geometry_columns", "raster_columns", "raster_overviews"):
        assert include_object(object(), relation, "view", True, None) is False


def test_alembic_keeps_application_spatial_objects() -> None:
    assert include_object(object(), "soil_samples", "table", True, object()) is True
