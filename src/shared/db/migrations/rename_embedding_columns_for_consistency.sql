-- Rename Embedding Columns Migration
-- Created: 2025-01-27
-- Purpose: Rename specific embedding column names to unified 'embedding' for consistency

-- Rename artists embedding column
ALTER TABLE artists RENAME COLUMN description_embedding TO embedding;

-- Rename venues embedding column
ALTER TABLE venues RENAME COLUMN venue_info_embedding TO embedding;

-- Rename genres embedding column
ALTER TABLE genres RENAME COLUMN genre_embedding TO embedding;

-- Rename events embedding column
ALTER TABLE events RENAME COLUMN event_text_embedding TO embedding;

-- Drop old indexes with specific names
DROP INDEX CONCURRENTLY IF EXISTS idx_artists_description_embedding;
DROP INDEX CONCURRENTLY IF EXISTS idx_venues_info_embedding;
DROP INDEX CONCURRENTLY IF EXISTS idx_genres_embedding;
DROP INDEX CONCURRENTLY IF EXISTS idx_events_text_embedding;

-- Create new indexes with unified naming
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artists_embedding
ON artists USING hnsw (embedding vector_cosine_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_venues_embedding
ON venues USING hnsw (embedding vector_cosine_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_genres_embedding
ON genres USING hnsw (embedding vector_cosine_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_embedding
ON events USING hnsw (embedding vector_cosine_ops);

-- Update comments for documentation
COMMENT ON COLUMN artists.embedding IS 'Vector embedding of artist name, description, website, and genre associations for semantic search';
COMMENT ON COLUMN venues.embedding IS 'Vector embedding of venue name, address, description, characteristics, and genre associations for semantic search';
COMMENT ON COLUMN genres.embedding IS 'Vector embedding of genre name and description for semantic search';
COMMENT ON COLUMN events.embedding IS 'Vector embedding of event name, description, and related information for semantic search';

COMMENT ON INDEX idx_artists_embedding IS 'HNSW index for fast cosine similarity search on artist embeddings';
COMMENT ON INDEX idx_venues_embedding IS 'HNSW index for fast cosine similarity search on venue embeddings';
COMMENT ON INDEX idx_genres_embedding IS 'HNSW index for fast cosine similarity search on genre embeddings';
COMMENT ON INDEX idx_events_embedding IS 'HNSW index for fast cosine similarity search on event embeddings';
