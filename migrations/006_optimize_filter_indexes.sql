-- Migration: Optimize filter query performance
-- Add indexes for region and industry filters

-- Index on region for US state filtering (most queries filter by state)
CREATE INDEX IF NOT EXISTS idx_profiles_region_filtered
    ON profiles(region)
    WHERE is_deleted = FALSE AND location_country = 'united states';

-- Index on industry for industry filtering
CREATE INDEX IF NOT EXISTS idx_profiles_industry_filtered
    ON profiles(industry)
    WHERE is_deleted = FALSE;

-- Composite index for common filter combinations (region + industry)
CREATE INDEX IF NOT EXISTS idx_profiles_region_industry
    ON profiles(region, industry)
    WHERE is_deleted = FALSE AND location_country = 'united states';

-- Index to speed up COUNT(*) queries with filters
CREATE INDEX IF NOT EXISTS idx_profiles_filters_count
    ON profiles(is_deleted, location_country, region, industry);
