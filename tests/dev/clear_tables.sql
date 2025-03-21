-- Disable foreign key checks temporarily
SET session_replication_role = 'replica';

-- Clear all tables in the correct order
TRUNCATE TABLE
    event_genres,
    artist_relations,
    events,
    artists,
    venues,
    genres
CASCADE;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

-- Reset any sequences
ALTER SEQUENCE events_id_seq RESTART WITH 1;
ALTER SEQUENCE artists_id_seq RESTART WITH 1;
ALTER SEQUENCE venues_id_seq RESTART WITH 1;
ALTER SEQUENCE genres_id_seq RESTART WITH 1;
