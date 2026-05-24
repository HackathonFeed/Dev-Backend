-- Add LeetCode-style public profile usernames
-- Run in Supabase SQL Editor after backend_schema.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(30);

UPDATE users
SET username = LEFT(
    COALESCE(NULLIF(REGEXP_REPLACE(LOWER(TRIM(name)), '[^a-z0-9]+', '-', 'g'), ''), 'user')
    || '-' || SUBSTRING(REPLACE(id::text, '-', ''), 1, 6),
    30
)
WHERE username IS NULL;

ALTER TABLE users ALTER COLUMN username SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
