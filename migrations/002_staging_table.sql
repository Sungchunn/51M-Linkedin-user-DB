-- ==========================================
-- INSIGHT - Semantic Talent Finder
-- Migration 002: Staging Table (Updated for USA_filtered.parquet)
-- ==========================================
-- This table mirrors the 62 columns from the actual Parquet file exactly
-- Used for fast COPY import before transformation to core schema

CREATE TABLE IF NOT EXISTS staging_profiles_raw (
    -- Primary identifiers (columns 1-3, 19-22, 26-27)
    "Full name" TEXT,
    "First Name" TEXT,
    "Middle Initial" TEXT,
    "Middle Name" TEXT,
    "Last Name" TEXT,
    "LinkedIn Url" TEXT,
    "LinkedIn Username" TEXT,

    -- Professional information (columns 2-4, 9, 49, 59-60)
    "Industry" TEXT,
    "Job title" TEXT,
    "Sub Role" TEXT,
    "Industry 2" TEXT,
    "Company Name" TEXT,
    "Job Summary" TEXT,
    "Years Experience" TEXT,
    "Summary" TEXT,

    -- Location (columns 14-17, 50-56)
    "Location" TEXT,
    "Locality" TEXT,
    "Metro" TEXT,
    "Region" TEXT,
    "Location Country" TEXT,
    "Location Continent" TEXT,
    "Street Address" TEXT,
    "Address Line 2" TEXT,
    "Postal Code" TEXT,
    "Location Geo" TEXT,

    -- Skills (column 18)
    "Skills" TEXT,

    -- Personal details (columns 23-25)
    "Birth Year" TEXT,
    "Birth Date" TEXT,
    "Gender" TEXT,

    -- Contact information (columns 6-8)
    "Emails" TEXT,
    "Mobile" TEXT,
    "Phone numbers" TEXT,

    -- Social profiles (columns 28-33)
    "Facebook Url" TEXT,
    "Facebook Username" TEXT,
    "Twitter Url" TEXT,
    "Twitter Username" TEXT,
    "Github Url" TEXT,
    "Github Username" TEXT,

    -- Company details (columns 10-13, 34-46)
    "Company Industry" TEXT,
    "Company Website" TEXT,
    "Company Size" TEXT,
    "Company Founded" TEXT,
    "Company Linkedin Url" TEXT,
    "Company Facebook Url" TEXT,
    "Company Twitter Url" TEXT,
    "Company Location Name" TEXT,
    "Company Location Locality" TEXT,
    "Company Location Metro" TEXT,
    "Company Location Region" TEXT,
    "Company Location Geo" TEXT,
    "Company Location Street Address" TEXT,
    "Company Location Address Line 2" TEXT,
    "Company Location Postal Code" TEXT,
    "Company Location Country" TEXT,
    "Company Location Continent" TEXT,

    -- Timestamps and metadata (columns 47-48, 56-58)
    "Last Updated" TEXT,
    "Start Date" TEXT,
    "Last Updated.1" TEXT,
    "Linkedin Connections" TEXT,
    "Inferred Salary" TEXT,

    -- Additional fields (columns 61-62)
    "Countries" TEXT,
    "Interests" TEXT,

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
'Staging table for raw parquet import. Mirrors USA_filtered.parquet 62 columns exactly.
Fast COPY import, no constraints. Transform to core schema after load.';
