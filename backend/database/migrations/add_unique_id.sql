-- Migration: Add unique_id column to companies table
-- Run this on Supabase SQL Editor if alembic doesn't auto-run

ALTER TABLE companies ADD COLUMN IF NOT EXISTS unique_id VARCHAR(50);
CREATE UNIQUE INDEX IF NOT EXISTS ix_companies_unique_id ON companies (unique_id);
