-- Add social media handles to users table
-- Run in Supabase SQL Editor after backend_schema.sql

ALTER TABLE users
ADD COLUMN IF NOT EXISTS github_username VARCHAR(100),
ADD COLUMN IF NOT EXISTS linkedin_username VARCHAR(100),
ADD COLUMN IF NOT EXISTS twitter_username VARCHAR(100),
ADD COLUMN IF NOT EXISTS website VARCHAR(255);
