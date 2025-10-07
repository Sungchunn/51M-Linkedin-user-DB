-- INSIGHT - Schema Design (Hot/Detail Split)
-- Optimized for M2 MacBook Air with 384-d vectors

-- Drop existing tables (careful!)
-- DROP TABLE IF EXISTS hot_audit CASCADE;
-- DROP TABLE IF EXISTS embedding_checkpoint CASCADE;
-- DROP TABLE IF EXISTS profiles_detail CASCADE;
-- DROP TABLE IF EXISTS profiles_hot CASCADE;

-- 1. profiles_hot (Narrow Serving Table)
-- Contains only essential fields for fast queries
-- 384-d vectors (60% smaller than 1536-d)
CREATE TABLE IF NOT EXISTS profiles_hot (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    linkedin_username VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,

    -- Professional (truncated for hot table)
    job_title VARCHAR(255),
    company_name VARCHAR(255),
    headline VARCHAR(500),                -- Truncated (full in detail table)

    -- Filters (indexed for fast queries)
    location_country VARCHAR(100),
    industry VARCHAR(100),
    seniority_level VARCHAR(50),
    years_experience INT,
    top_skills TEXT[],                    -- Top 10 skills only

    -- 384-d vector (reduced from 1536-d for disk savings)
    embedding VECTOR(384),
    embedding_generated_at TIMESTAMPTZ,
    content_hash CHAR(32),                -- MD5 for deduplication

    -- Hotness ranking
    quality_score DECIMAL(3,2) CHECK (quality_score >= 0 AND quality_score <= 1),
    hotness_score DECIMAL(10,2) DEFAULT 0,
    query_count_7d INT DEFAULT 0,
    click_count_7d INT DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_promoted_at TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- 2. profiles_detail (Long Fields)
-- Joined on-demand for full profile view
CREATE TABLE IF NOT EXISTS profiles_detail (
    id UUID PRIMARY KEY REFERENCES profiles_hot(id) ON DELETE CASCADE,

    -- Long text fields
    summary TEXT,                         -- Full summary

    -- Structured data (JSONB for flexibility)
    experience_json JSONB,
    education_json JSONB,
    certifications_json JSONB,

    -- Contact (sensitive)
    email VARCHAR(255),
    phone VARCHAR(50),
    website VARCHAR(500),

    -- Social
    twitter VARCHAR(255),
    github VARCHAR(255),

    -- Complete skills (all, not just top 10)
    all_skills TEXT[],

    -- Metadata
    profile_completeness INT CHECK (profile_completeness >= 0 AND profile_completeness <= 100),
    linkedin_url TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. hot_audit (Promotion/Demotion Tracking)
CREATE TABLE IF NOT EXISTS hot_audit (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,          -- 'promote_hot', 'demote_hot', etc.
    affected_count INT DEFAULT 0,
    details JSONB,
    performed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. embedding_checkpoint (Resumable Pipeline)
CREATE TABLE IF NOT EXISTS embedding_checkpoint (
    id SERIAL PRIMARY KEY,
    batch_name VARCHAR(100) UNIQUE NOT NULL,
    last_processed_id UUID,
    rows_processed INT DEFAULT 0,
    rows_embedded INT DEFAULT 0,
    rows_skipped INT DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Auto-update triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profiles_hot_updated_at
    BEFORE UPDATE ON profiles_hot
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_detail_updated_at
    BEFORE UPDATE ON profiles_detail
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Verify tables
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('profiles_hot', 'profiles_detail', 'hot_audit', 'embedding_checkpoint')
ORDER BY tablename;
