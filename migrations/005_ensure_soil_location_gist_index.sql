-- Ensure the spatial index exists for location-based reports and map queries.
-- This also upgrades databases that were created with create_all before the
-- index was declared in the SQLAlchemy model metadata.
CREATE INDEX IF NOT EXISTS idx_soil_samples_location
    ON soil_samples USING GIST (location);
