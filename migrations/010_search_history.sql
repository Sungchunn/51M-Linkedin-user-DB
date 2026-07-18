-- Migration 010: Search History Table
-- Per-user persistence for the frontend search-history sidebar
-- (frontend/lib/searchHistory.js is the single client access point that swaps
--  localStorage for the /history endpoints)

CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(300) NOT NULL,
    params JSONB NOT NULL,
    params_signature CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT search_history_label_not_empty CHECK (length(trim(label)) > 0),
    CONSTRAINT search_history_signature_length CHECK (length(params_signature) = 64),
    CONSTRAINT search_history_updated_after_created CHECK (updated_at >= created_at),
    CONSTRAINT search_history_unique_per_user UNIQUE (user_id, params_signature)
);

-- Newest-first listing per user is the only read path
CREATE INDEX idx_search_history_user_recency ON search_history(user_id, updated_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON search_history TO postgres;

COMMENT ON TABLE search_history IS 'Per-user saved searches backing the sidebar history (capped at 50 per user, enforced by the API on insert)';
COMMENT ON COLUMN search_history.params IS 'Frontend search form params, opaque to the API — stored verbatim and replayed by the client';
COMMENT ON COLUMN search_history.params_signature IS 'SHA-256 hex of canonical (sorted-keys, compact) params JSON; dedup key so re-running a search bumps the existing row instead of duplicating';
COMMENT ON COLUMN search_history.updated_at IS 'Last time this search was run — recency key exposed to the client as ts (epoch ms)';
