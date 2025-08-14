-- Vector Embeddings Enhancement Migration
-- Created: 2025-08-13
-- Purpose: Add vector embedding columns to core tables for semantic search and RAG capabilities

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector embedding columns to artists table
ALTER TABLE artists ADD COLUMN IF NOT EXISTS description_embedding VECTOR(384);

-- Add vector embedding columns to venues table
ALTER TABLE venues ADD COLUMN IF NOT EXISTS venue_info_embedding VECTOR(384);

-- Add vector embedding columns to genres table
ALTER TABLE genres ADD COLUMN IF NOT EXISTS genre_embedding VECTOR(384);

-- Create HNSW indexes for efficient similarity search
-- Using vector_cosine_ops for cosine similarity search
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artists_description_embedding
ON artists USING hnsw (description_embedding vector_cosine_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_venues_info_embedding
ON venues USING hnsw (venue_info_embedding vector_cosine_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_genres_embedding
ON genres USING hnsw (genre_embedding vector_cosine_ops);

-- Add comments for documentation
COMMENT ON COLUMN artists.description_embedding IS 'Vector embedding of artist name, description, website, and genre associations for semantic search';
COMMENT ON COLUMN venues.venue_info_embedding IS 'Vector embedding of venue name, address, description, characteristics, and genre associations for semantic search';
COMMENT ON COLUMN genres.genre_embedding IS 'Vector embedding of genre name and description for semantic search';

COMMENT ON INDEX idx_artists_description_embedding IS 'HNSW index for fast cosine similarity search on artist embeddings';
COMMENT ON INDEX idx_venues_info_embedding IS 'HNSW index for fast cosine similarity search on venue embeddings';
COMMENT ON INDEX idx_genres_embedding IS 'HNSW index for fast cosine similarity search on genre embeddings';
