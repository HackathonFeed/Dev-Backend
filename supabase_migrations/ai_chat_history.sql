-- ============================================================
-- AI Chat History Tables
-- Run in Supabase Dashboard → SQL Editor
-- ============================================================

-- Chat sessions (one per conversation thread)
CREATE TABLE IF NOT EXISTS public.ai_chat_sessions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL,               -- references app users.id
    title              TEXT NOT NULL DEFAULT 'New Chat',
    hackathon_context  JSONB,                        -- stored hackathon context blob
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chat messages within a session
CREATE TABLE IF NOT EXISTS public.ai_chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_session FOREIGN KEY (session_id)
        REFERENCES public.ai_chat_sessions(id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_user_updated
    ON public.ai_chat_sessions(user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session_created
    ON public.ai_chat_messages(session_id, created_at ASC);

-- Enable Row Level Security
-- (service key bypasses RLS, but good security practice)
ALTER TABLE public.ai_chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_chat_messages ENABLE ROW LEVEL SECURITY;
