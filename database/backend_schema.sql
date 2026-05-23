-- ============================================================================
-- HackathonFeed Backend Tables (run in Supabase SQL Editor)
-- Requires existing hackathons table from scraper schema
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'user',
    interests TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS bookmarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hackathon_id UUID NOT NULL REFERENCES hackathons(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_hackathon_bookmark UNIQUE (user_id, hackathon_id)
);

CREATE INDEX IF NOT EXISTS ix_bookmarks_user_id ON bookmarks (user_id);
CREATE INDEX IF NOT EXISTS ix_bookmarks_hackathon_id ON bookmarks (hackathon_id);

CREATE TABLE IF NOT EXISTS analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(255),
    user_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analytics_events_event_type ON analytics_events (event_type);
CREATE INDEX IF NOT EXISTS ix_analytics_events_user_id ON analytics_events (user_id);
CREATE INDEX IF NOT EXISTS ix_analytics_events_created_at ON analytics_events (created_at);

CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT,
    filters JSONB,
    result_count INTEGER NOT NULL DEFAULT 0,
    user_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_search_logs_user_id ON search_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_search_logs_created_at ON search_logs (created_at);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service role full access users"
    ON users FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service role full access bookmarks"
    ON bookmarks FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service role full access analytics"
    ON analytics_events FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service role full access search_logs"
    ON search_logs FOR ALL TO service_role USING (true) WITH CHECK (true);
