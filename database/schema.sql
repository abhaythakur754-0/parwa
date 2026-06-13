-- ════════════════════════════════════════════════════════════════
-- PARWA — Database Initialization Script
-- ════════════════════════════════════════════════════════════════
-- This file is mounted into the PostgreSQL container at startup.
-- It runs BEFORE Alembic migrations. Its purpose is to ensure
-- the database exists and has the pgvector extension enabled.
--
-- ⚠️  IMPORTANT: Schema creation is handled by Alembic migrations
--     in database/alembic/versions/. Do NOT add CREATE TABLE here.
-- ════════════════════════════════════════════════════════════════

-- Enable pgvector extension for AI embedding storage (required by RAG/knowledge base)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;

-- Grant permissions to the application user
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parwa') THEN
        GRANT ALL PRIVILEGES ON DATABASE parwa_db TO parwa;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO parwa;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO parwa;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO parwa;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO parwa;
    END IF;
END
$$;

-- Set default timezone
SET timezone = 'UTC';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'PARWA database initialized successfully. pgvector and extensions ready.';
END
$$;
