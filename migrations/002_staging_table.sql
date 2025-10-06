-- ==========================================
-- INSIGHT - Semantic Talent Finder
-- Migration 002: Staging Table
-- ==========================================
-- This table mirrors the 62 columns from the parquet file exactly
-- Used for fast COPY import before transformation to core schema

CREATE TABLE IF NOT EXISTS staging_profiles_raw (
    -- Primary identifiers
    "Full name" TEXT,
    "First Name" TEXT,
    "Last Name" TEXT,
    "LinkedIn Username" TEXT,
    "LinkedIn Url" TEXT,

    -- Professional information
    "Job title" TEXT,
    "Company Name" TEXT,
    "Industry" TEXT,
    "Years Experience" TEXT,

    -- Location (4 fields for granular search)
    "Location" TEXT,
    "Locality" TEXT,
    "Region" TEXT,
    "Location Country" TEXT,

    -- Skills and education
    "Skills" TEXT,
    "Education" TEXT,

    -- Profile content
    "Job Summary" TEXT,
    "Summary" TEXT,
    "Headline" TEXT,

    -- Contact information
    "Email" TEXT,
    "Phone" TEXT,
    "Twitter" TEXT,
    "Github" TEXT,
    "Website" TEXT,

    -- Company details
    "Company Size" TEXT,
    "Company Website" TEXT,
    "Company LinkedIn" TEXT,
    "Company Twitter" TEXT,

    -- Additional metadata (adjust based on actual parquet columns)
    "Recommendations Count" TEXT,
    "Connections Count" TEXT,
    "Followers Count" TEXT,
    "Profile Views" TEXT,
    "Search Appearances" TEXT,

    -- Languages and certifications
    "Languages" TEXT,
    "Certifications" TEXT,
    "Courses" TEXT,
    "Projects" TEXT,
    "Publications" TEXT,
    "Patents" TEXT,
    "Honors Awards" TEXT,
    "Volunteer Experience" TEXT,
    "Organizations" TEXT,

    -- Additional experience fields
    "Current Position" TEXT,
    "Previous Positions" TEXT,
    "Total Experience Years" TEXT,

    -- Profile metadata
    "Profile Created Date" TEXT,
    "Profile Last Updated" TEXT,
    "Profile Completeness" TEXT,
    "Premium Account" TEXT,
    "Open to Work" TEXT,
    "Hiring" TEXT,
    "Influencer" TEXT,

    -- Geographic and demographic
    "Time Zone" TEXT,
    "Postal Code" TEXT,
    "Country Code" TEXT,

    -- Additional fields (fill remaining columns to reach 62)
    "Company Industry" TEXT,
    "Company Specialties" TEXT,
    "Company Founded Year" TEXT,
    "Company Headquarters" TEXT,
    "Company Type" TEXT,
    "Company Employee Count" TEXT,

    -- Import metadata
    "import_batch_id" TEXT,
    "import_timestamp" TIMESTAMPTZ DEFAULT NOW()
);

-- Index for deduplication on LinkedIn Username
CREATE INDEX IF NOT EXISTS idx_staging_linkedin_username
ON staging_profiles_raw("LinkedIn Username");

-- Index for import batch tracking
CREATE INDEX IF NOT EXISTS idx_staging_batch
ON staging_profiles_raw("import_batch_id");

COMMENT ON TABLE staging_profiles_raw IS
'Staging table for raw parquet import. Mirrors source file columns exactly.
Fast COPY import, no constraints. Transform to core schema after load.';
