-- INSIGHT - Extension Setup
-- Install required PostgreSQL extensions

-- UUID generation (needed for uuid_generate_v4())
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Full-text search with trigrams (fuzzy matching)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN indexes for composite types
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Verify extensions
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('uuid-ossp', 'vector', 'pg_trgm', 'btree_gin')
ORDER BY extname;
