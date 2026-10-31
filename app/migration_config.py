"""Alembic autogeneration filters for application-owned database objects."""

from geoalchemy2 import alembic_helpers

POSTGIS_MANAGED_RELATIONS = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
}
APPLICATION_SCHEMA = "public"


def include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],
) -> bool:
    """Limit reflection to the application's default PostgreSQL schema."""

    if type_ == "schema":
        return name in {None, APPLICATION_SCHEMA}

    if type_ == "table":
        return parent_names.get("schema_name") in {None, APPLICATION_SCHEMA}

    return True


def include_object(
    object_: object,
    name: str,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Exclude PostGIS-owned catalog relations from application diffs."""

    if not alembic_helpers.include_object(object_, name, type_, reflected, compare_to):
        return False

    if type_ in {"table", "view"} and reflected and name in POSTGIS_MANAGED_RELATIONS:
        return False
    return True
