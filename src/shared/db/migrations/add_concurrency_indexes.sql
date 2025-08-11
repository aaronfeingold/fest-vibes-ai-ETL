-- Database Concurrency Optimization Indexes
-- Created: 2025-08-07
-- Purpose: Add indexes to support concurrent UPSERT operations and prevent deadlocks

-- Artists table - enable atomic upserts by name
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_artists_name ON artists(name);

-- Venues table - composite key for venue uniqueness (name + address)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_venues_name_address ON venues(name, full_address);

-- Events table - prevent duplicate events by WWOZ href
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_events_href ON events(wwoz_event_href);

-- Performance indexes for common foreign key lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_artist_venue ON events(artist_id, venue_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_performance_time ON events(performance_time);

-- Artist relations table - prevent duplicate relationships
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_artist_relations_unique ON artist_relations(artist_id, related_artist_id);

-- Genre name already has unique constraint, but ensure index exists for performance
-- (This should already exist from the unique constraint, but adding for completeness)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_genres_name ON genres(name);

-- Add indexes for common join patterns in association tables
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_genres_event_id ON event_genres(event_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_genres_genre_id ON event_genres(genre_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artist_genres_artist_id ON artist_genres(artist_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artist_genres_genre_id ON artist_genres(genre_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_venue_genres_venue_id ON venue_genres(venue_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_venue_genres_genre_id ON venue_genres(genre_id);

-- Comments for documentation
COMMENT ON INDEX idx_artists_name IS 'Enables atomic UPSERT operations for artists by name';
COMMENT ON INDEX idx_venues_name_address IS 'Composite unique constraint for venue identification';
COMMENT ON INDEX idx_events_href IS 'Prevents duplicate events using WWOZ href as unique identifier';
COMMENT ON INDEX idx_events_artist_venue IS 'Performance index for common artist-venue event queries';
COMMENT ON INDEX idx_events_performance_time IS 'Performance index for time-based event queries';
