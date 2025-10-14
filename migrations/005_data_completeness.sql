-- ==========================================
-- INSIGHT - Data Completeness Enhancement
-- Migration 005: Add data_completeness_pct column
-- ==========================================

-- Purpose: Track profile data quality for filtering
-- Use case: GTM teams want profiles with contact info for outreach
-- Priority: HIGH - Essential for production use

-- Add data completeness percentage column
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS data_completeness_pct INT DEFAULT 0 CHECK (data_completeness_pct >= 0 AND data_completeness_pct <= 100);

-- Create index for filtering by completeness
CREATE INDEX IF NOT EXISTS idx_profiles_data_completeness
ON profiles(data_completeness_pct)
WHERE is_deleted = FALSE;

-- Calculate data completeness for existing profiles
-- Scoring:
--   Email: 10 points
--   Phone: 10 points
--   LinkedIn URL: 15 points
--   Summary (>50 chars): 20 points
--   Skills (has items): 15 points
--   Years Experience: 10 points
--   Location Country: 10 points
--   Company Name: 10 points
-- Total: 100 points

UPDATE profiles SET data_completeness_pct = (
    (CASE WHEN email IS NOT NULL THEN 10 ELSE 0 END) +
    (CASE WHEN phone IS NOT NULL THEN 10 ELSE 0 END) +
    (CASE WHEN linkedin_url IS NOT NULL THEN 15 ELSE 0 END) +
    (CASE WHEN summary IS NOT NULL AND length(summary) > 50 THEN 20 ELSE 0 END) +
    (CASE WHEN skills IS NOT NULL AND array_length(skills, 1) > 0 THEN 15 ELSE 0 END) +
    (CASE WHEN years_experience IS NOT NULL THEN 10 ELSE 0 END) +
    (CASE WHEN location_country IS NOT NULL THEN 10 ELSE 0 END) +
    (CASE WHEN company_name IS NOT NULL THEN 10 ELSE 0 END)
)
WHERE data_completeness_pct = 0;  -- Only update unset values

-- Add comment for documentation
COMMENT ON COLUMN profiles.data_completeness_pct IS
'Data quality score (0-100). Higher = more fields populated.
Used for filtering profiles with contact info for outreach campaigns.';

-- Create index for common completeness thresholds
CREATE INDEX IF NOT EXISTS idx_profiles_high_completeness
ON profiles(data_completeness_pct)
WHERE data_completeness_pct >= 70 AND is_deleted = FALSE;

-- Analyze table for query planner optimization
ANALYZE profiles;
