-- ── Semantic search for devfolio_projects using pgvector ──────────────────────
--
-- After running this migration, run once:
--   python scripts/generate_project_embeddings.py
--
-- For new projects added by the scraper, call:
--   POST /api/v1/admin/generate-embeddings   (admin JWT required)
-- OR use pg_cron (see bottom of this file) for fully automated scheduling.
-- ─────────────────────────────────────────────────────────────────────────────
-- Run this in Supabase SQL Editor

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding column (1024 dims = Amazon Titan Embed v2 default)
ALTER TABLE public.devfolio_projects
ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- 3. HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS devfolio_projects_embedding_hnsw
ON public.devfolio_projects
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Semantic search RPC function
--    Called from Python: client.rpc("match_projects", {...}).execute()
CREATE OR REPLACE FUNCTION match_projects(
    query_embedding  vector(1024),
    match_count      int     DEFAULT 5,
    filter_winner    boolean DEFAULT false,
    filter_technology text   DEFAULT NULL
)
RETURNS TABLE (
    id               uuid,
    title            text,
    tagline          text,
    url              text,
    thumbnail        text,
    technologies     text[],
    hackathon_name   text,
    hackathon_url    text,
    likes_count      int,
    views            int,
    is_winner        boolean,
    github_url       text,
    demo_url         text,
    prize            text,
    prize_description text,
    team_members     jsonb,
    description_sections jsonb,
    source_platform  text,
    scraped_at       timestamptz,
    similarity       float
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.title,
        p.tagline,
        p.url,
        p.thumbnail,
        p.technologies,
        p.hackathon_name,
        p.hackathon_url,
        p.likes_count,
        p.views,
        p.is_winner,
        p.github_url,
        p.demo_url,
        p.prize,
        p.prize_description,
        p.team_members::jsonb,
        p.description_sections::jsonb,
        p.source_platform,
        p.scraped_at,
        1 - (p.embedding <=> query_embedding) AS similarity
    FROM public.devfolio_projects p
    WHERE
        p.embedding IS NOT NULL
        AND (NOT filter_winner OR p.is_winner = true)
        AND (filter_technology IS NULL OR p.technologies @> ARRAY[filter_technology])
    ORDER BY p.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;


-- ── Helper: count projects that still need embeddings ─────────────────────────
-- Quick health check: SELECT * FROM projects_needing_embeddings();
CREATE OR REPLACE FUNCTION projects_needing_embeddings()
RETURNS TABLE (count bigint)
LANGUAGE sql STABLE AS $$
    SELECT COUNT(*) FROM public.devfolio_projects WHERE embedding IS NULL;
$$;


-- ── Optional: pg_cron automated scheduling ───────────────────────────────────
-- Supabase supports pg_cron. Enable it in:
--   Dashboard → Database → Extensions → pg_cron
--
-- This schedules the FastAPI embedding endpoint to be called every hour.
-- Replace YOUR_BACKEND_URL and YOUR_ADMIN_JWT with real values.
--
-- CREATE EXTENSION IF NOT EXISTS pg_cron;
--
-- SELECT cron.schedule(
--   'generate-embeddings-hourly',
--   '0 * * * *',   -- every hour at :00
--   $$
--     SELECT net.http_post(
--       url := 'YOUR_BACKEND_URL/api/v1/admin/generate-embeddings',
--       headers := '{"Authorization": "Bearer YOUR_ADMIN_JWT", "Content-Type": "application/json"}'::jsonb,
--       body := '{}'::jsonb
--     )
--   $$
-- );
