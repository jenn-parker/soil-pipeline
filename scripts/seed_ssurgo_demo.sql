-- Loads representative soil-survey records for the local demo map.
-- Source: USDA NRCS Soil Data Access / SSURGO surface horizons.
-- These are map-unit representative locations, not farm-collected samples.

INSERT INTO soil_samples (
    sample_id, field_name, sampled_at, latitude, longitude, location,
    soil_ph, organic_matter_pct, sand_pct, silt_pct, clay_pct
)
SELECT
    seed.sample_id,
    seed.field_name,
    seed.sampled_at::timestamptz,
    seed.latitude,
    seed.longitude,
    ST_SetSRID(ST_MakePoint(seed.longitude, seed.latitude), 4326)::geography,
    seed.soil_ph,
    seed.organic_matter_pct,
    seed.sand_pct,
    seed.silt_pct,
    seed.clay_pct
FROM (VALUES
    ('ssurgo-ia-ames', 'SSURGO representative / Ames', '2026-01-01T00:00:00Z', 42.03, -93.62, 6.20, 3.50, 45.00, 34.00, 21.00),
    ('ssurgo-ia-boone', 'SSURGO representative / Boone', '2026-01-01T00:00:00Z', 42.06, -93.88, 6.50, 3.50, 41.60, 37.40, 21.00),
    ('ssurgo-ia-iowa-city', 'SSURGO representative / Iowa City', '2026-01-01T00:00:00Z', 41.66, -91.53, 6.00, 3.00, 3.00, 74.00, 23.00),
    ('ssurgo-ia-cedar-rapids', 'SSURGO representative / Cedar Rapids', '2026-01-01T00:00:00Z', 42.00, -91.67, 6.10, 1.25, 85.00, 10.00, 5.00),
    ('ssurgo-ia-council-bluffs', 'SSURGO representative / Council Bluffs', '2026-01-01T00:00:00Z', 41.26, -95.86, 6.70, 3.00, 9.50, 67.50, 23.00),
    ('ssurgo-ia-sioux-city', 'SSURGO representative / Sioux City', '2026-01-01T00:00:00Z', 42.50, -96.40, 6.20, 3.40, 4.00, 73.00, 23.00),
    ('ssurgo-ia-dubuque', 'SSURGO representative / Dubuque', '2026-01-01T00:00:00Z', 42.50, -90.66, 6.10, 3.00, 60.00, 31.00, 9.00),
    ('ssurgo-ia-fort-dodge', 'SSURGO representative / Fort Dodge', '2026-01-01T00:00:00Z', 42.50, -94.17, 6.70, 5.50, 39.10, 36.90, 24.00),
    ('ssurgo-ia-mason-city', 'SSURGO representative / Mason City', '2026-01-01T00:00:00Z', 43.15, -93.20, 6.30, 1.00, 35.00, 40.00, 25.00),
    ('ssurgo-ia-ottumwa', 'SSURGO representative / Ottumwa', '2026-01-01T00:00:00Z', 41.00, -92.00, 5.90, 3.00, 5.00, 73.00, 22.00)
) AS seed(sample_id, field_name, sampled_at, latitude, longitude, soil_ph, organic_matter_pct, sand_pct, silt_pct, clay_pct)
ON CONFLICT (sample_id) DO NOTHING;

SELECT COUNT(*) AS seeded_ssurgo_records
FROM soil_samples
WHERE sample_id LIKE 'ssurgo-ia-%';
