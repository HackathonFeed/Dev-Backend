-- Profile photos: users.avatar_url + Supabase Storage bucket
-- Run in Supabase SQL Editor after backend_schema.sql / add_user_username.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);

-- Public bucket for profile photos (5 MB, images only)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'avatars',
    'avatars',
    true,
    5242880,
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']::text[]
)
ON CONFLICT (id) DO UPDATE SET
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Anyone can view avatar images (public profiles)
DO $$ BEGIN
    CREATE POLICY "Public avatar read"
        ON storage.objects
        FOR SELECT
        USING (bucket_id = 'avatars');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Backend uses the service role key for uploads/deletes (bypasses RLS)
