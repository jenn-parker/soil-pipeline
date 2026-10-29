CREATE TABLE IF NOT EXISTS soil_upload_batches (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'processing',
    total_rows INTEGER NOT NULL DEFAULT 0,
    accepted_rows INTEGER NOT NULL DEFAULT 0,
    rejected_rows INTEGER NOT NULL DEFAULT 0,
    errors JSON NOT NULL DEFAULT '[]'::json,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL
);

ALTER TABLE soil_samples
    ADD COLUMN IF NOT EXISTS batch_id INTEGER NULL
    REFERENCES soil_upload_batches(id);

CREATE INDEX IF NOT EXISTS ix_soil_samples_batch_id
    ON soil_samples (batch_id);
