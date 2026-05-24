-- ============================================================================
-- HackathonFeed Tracked Projects (run in Supabase SQL Editor)
-- Requires: users, hackathons tables already exist
-- Safe to re-run (uses IF NOT EXISTS / duplicate_object guards)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE journey_step_id AS ENUM (
        'registered', 'project_created', 'building', 'submitted', 'accepted'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tracked_stage AS ENUM (
        'Idea / Backlog', 'In Progress', 'Submitted', 'Accepted / Win'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE timeline_event_type AS ENUM (
        'registered', 'bookmarked', 'project_created', 'building', 'submitted',
        'accepted', 'stage_changed', 'milestone_completed', 'milestone_added',
        'team_member_added', 'idea_validated', 'note'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS tracked_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hackathon_id UUID NOT NULL REFERENCES hackathons(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'Untitled project',
    concept TEXT NOT NULL DEFAULT '',
    stage tracked_stage NOT NULL DEFAULT 'Idea / Backlog',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_hackathon_track UNIQUE (user_id, hackathon_id)
);

CREATE INDEX IF NOT EXISTS ix_tracked_projects_user_id ON tracked_projects (user_id);
CREATE INDEX IF NOT EXISTS ix_tracked_projects_hackathon_id ON tracked_projects (hackathon_id);
CREATE INDEX IF NOT EXISTS ix_tracked_projects_updated_at ON tracked_projects (updated_at DESC);

CREATE TABLE IF NOT EXISTS tracked_project_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
    step_id journey_step_id NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_step UNIQUE (project_id, step_id)
);

CREATE INDEX IF NOT EXISTS ix_tracked_project_steps_project_id ON tracked_project_steps (project_id);

CREATE TABLE IF NOT EXISTS tracked_project_timeline_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
    event_type timeline_event_type NOT NULL,
    label VARCHAR(255) NOT NULL,
    description TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tracked_timeline_project_id ON tracked_project_timeline_events (project_id);
CREATE INDEX IF NOT EXISTS ix_tracked_timeline_occurred_at ON tracked_project_timeline_events (occurred_at);

CREATE TABLE IF NOT EXISTS tracked_project_milestones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tracked_milestones_project_id ON tracked_project_milestones (project_id);

CREATE TABLE IF NOT EXISTS tracked_project_team_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
    role_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tracked_team_project_id ON tracked_project_team_members (project_id);

ALTER TABLE tracked_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracked_project_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracked_project_timeline_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracked_project_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracked_project_team_members ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "service role full access tracked_projects"
        ON tracked_projects FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY "service role full access tracked_project_steps"
        ON tracked_project_steps FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY "service role full access tracked_project_timeline_events"
        ON tracked_project_timeline_events FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY "service role full access tracked_project_milestones"
        ON tracked_project_milestones FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY "service role full access tracked_project_team_members"
        ON tracked_project_team_members FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
