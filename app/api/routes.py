"""Compatibility facade for the API router and commonly imported handlers.

Route implementations live in domain-specific modules. This module preserves the
original import path for application code and tests while the API is decomposed.
"""

from app.api.access import grant_sample_access, list_sample_access, revoke_sample_access
from app.api.batches import get_soil_batch, upload_soil_batch
from app.api.dependencies import (
    _accessible_sample_filter,
    _get_editable_sample,
    _get_owned_sample,
    _principal,
    make_wgs84_point,
)
from app.api.maps import get_soil_samples_geojson
from app.api.provenance import create_party, create_sample_provenance
from app.api.reports import (
    SOIL_MEASUREMENT_ATTRIBUTES,
    SOIL_MEASUREMENTS,
    create_location_recommendation_brief,
    get_soil_range_report,
)
from app.api.router import router
from app.api.samples import (
    archive_soil_test_result,
    create_soil_test_result,
    delete_soil_test_result,
    get_soil_test_result,
    list_owned_soil_samples,
    restore_soil_test_result,
    update_soil_test_result,
)

__all__ = ["router"]
