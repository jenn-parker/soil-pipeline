DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'soil_samples'
          AND column_name = 'sampled_at'
          AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE soil_samples
            ALTER COLUMN sampled_at TYPE TIMESTAMPTZ
            USING sampled_at AT TIME ZONE 'UTC';
    END IF;
END
$$;
