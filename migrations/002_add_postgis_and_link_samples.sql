CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE soil_samples
    ADD COLUMN IF NOT EXISTS location geography(POINT, 4326);

ALTER TABLE sample_identifications
    ADD COLUMN IF NOT EXISTS soil_sample_id INTEGER NULL
    REFERENCES soil_samples(id);

UPDATE sample_identifications AS identification
SET soil_sample_id = soil_sample.id
FROM soil_samples AS soil_sample
WHERE identification.soil_sample_id IS NULL
  AND identification.sample_id = soil_sample.sample_id;

UPDATE soil_samples AS soil_sample
SET latitude = identification.latitude,
    longitude = identification.longitude
FROM sample_identifications AS identification
WHERE identification.soil_sample_id = soil_sample.id
  AND (soil_sample.latitude IS NULL OR soil_sample.longitude IS NULL)
  AND identification.latitude IS NOT NULL
  AND identification.longitude IS NOT NULL;

UPDATE soil_samples
SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
WHERE location IS NULL
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_sample_identifications_soil_sample_id
    ON sample_identifications (soil_sample_id);

CREATE INDEX IF NOT EXISTS idx_soil_samples_location
    ON soil_samples USING GIST (location);
