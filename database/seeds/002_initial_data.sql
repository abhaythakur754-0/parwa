-- PARWA — Initial Seed Data
-- Default variant and technique configurations

-- Default technique configurations (only insert if table exists and is empty)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'technique_configuration') THEN
        IF NOT EXISTS (SELECT 1 FROM technique_configuration LIMIT 1) THEN
            -- Seed data will be populated by Alembic migrations
            NULL;
        END IF;
    END IF;
END $$;
