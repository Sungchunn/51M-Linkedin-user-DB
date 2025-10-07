-- INSIGHT - Extension Setup
-- Install required PostgreSQL extensions

-- Vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Full-text search with trigrams (fuzzy matching)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN indexes for composite types
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Verify extensions
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('vector', 'pg_trgm', 'btree_gin')
ORDER BY extname;
