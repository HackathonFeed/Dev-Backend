-- Migration: Add subscription plan and AI points to users table
-- Run in Supabase SQL editor

-- 1. Create enum type
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_plan') THEN
    CREATE TYPE subscription_plan AS ENUM ('hacker', 'builder', 'champion');
  END IF;
END$$;

-- 2. Add columns
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS subscription_plan subscription_plan NOT NULL DEFAULT 'hacker',
  ADD COLUMN IF NOT EXISTS ai_points         INTEGER           NOT NULL DEFAULT 50,
  ADD COLUMN IF NOT EXISTS plan_expires_at   TIMESTAMPTZ;

-- 3. Backfill existing users with Hacker defaults (already covered by DEFAULT)
UPDATE users SET subscription_plan = 'hacker', ai_points = 50 WHERE subscription_plan IS NULL;
