-- ==========================================
-- INSIGHT - Semantic Talent Finder
-- Migration 003: Core Schema with Negative Spaces
-- ==========================================

-- Main profiles table with strict constraints (Negative Spaces)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Core identity (NEGATIVE SPACE: Cannot be null or empty)
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    first_name TEXT,
    last_name TEXT,
    linkedin_url TEXT,
    linkedin_username TEXT UNIQUE NOT NULL CHECK (linkedin_username ~ '^[a-zA-Z0-9_-]+$'),

    -- Professional information
    job_title TEXT,
    company_name TEXT,
    industry TEXT,
    years_experience INT CHECK (years_experience >= 0 AND years_experience <= 80),

    -- Location (4-level granularity for hybrid search)
    location TEXT,
    locality TEXT,
    region TEXT,
    location_country TEXT,

    -- Skills (array for GIN indexing)
    skills TEXT[],
    skills_normalized TEXT[],

    -- Profile content
    headline TEXT,
    summary TEXT,

    -- Contact
    email TEXT CHECK (email IS NULL OR email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),
    phone TEXT,
    website TEXT,

    -- Social profiles
    twitter TEXT,
    github TEXT,

    -- Embedding for vector search (NEGATIVE SPACE: Must be 1536 dims or NULL)
    embedding VECTOR(1536),

    -- Quality metadata
    content_quality_score DECIMAL(3,2) CHECK (content_quality_score >= 0 AND content_quality_score <= 1),
    profile_completeness INT CHECK (profile_completeness >= 0 AND profile_completeness <= 100),

    -- Timestamps (NEGATIVE SPACE: created <= updated, deleted >= created)
    created_at TIMESTAMPTZ DEFAULT NOW() CHECK (created_at <= NOW()),
    updated_at TIMESTAMPTZ DEFAULT NOW() CHECK (updated_at >= created_at),
    deleted_at TIMESTAMPTZ CHECK (deleted_at IS NULL OR deleted_at >= created_at),

    -- Soft delete flag
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Companies table (normalized)
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL CHECK (length(trim(name)) > 0),
    industry TEXT,
    size_range TEXT,
    founded_year INT CHECK (founded_year >= 1800 AND founded_year <= EXTRACT(YEAR FROM NOW())),
    headquarters_country TEXT,
    headquarters_city TEXT,
    website TEXT,
    linkedin_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Profile experiences (work history)
CREATE TABLE IF NOT EXISTS profile_experiences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id),
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    start_date DATE,
    end_date DATE CHECK (end_date IS NULL OR end_date >= start_date),
    is_current BOOLEAN DEFAULT FALSE,
    description TEXT,
    location TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Education records
CREATE TABLE IF NOT EXISTS profile_education (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    institution TEXT NOT NULL,
    degree TEXT,
    field_of_study TEXT,
    start_year INT CHECK (start_year >= 1900),
    end_year INT CHECK (end_year IS NULL OR end_year >= start_year),
    grade TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Certifications
CREATE TABLE IF NOT EXISTS profile_certifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    issuing_organization TEXT,
    issue_date DATE,
    expiration_date DATE CHECK (expiration_date IS NULL OR expiration_date >= issue_date),
    credential_id TEXT,
    credential_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comments on tables
COMMENT ON TABLE profiles IS
'Core profiles table with strict Negative Space constraints.
linkedin_username is the natural key (unique, immutable).
embedding is 1536-dim vector for semantic search.';

COMMENT ON TABLE companies IS
'Normalized company data to reduce redundancy in profiles table.';

COMMENT ON TABLE profile_experiences IS
'Work history with CASCADE delete when profile is removed.';

COMMENT ON COLUMN profiles.embedding IS
'1536-dimensional vector from text-embedding-3-small.
NULL if quality score < threshold (0.7).';

COMMENT ON COLUMN profiles.years_experience IS
'NEGATIVE SPACE: Must be [0, 80]. Values outside this range indicate data error.';

COMMENT ON COLUMN profiles.linkedin_username IS
'NEGATIVE SPACE: Must match ^[a-zA-Z0-9_-]+$ pattern. Natural key for dedup.';
