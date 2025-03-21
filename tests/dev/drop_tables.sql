-- Disable foreign key checks temporarily
SET session_replication_role = 'replica';

-- Drop all tables
DROP TABLE IF EXISTS event_genres CASCADE;
DROP TABLE IF EXISTS artist_relations CASCADE;
DROP TABLE IF EXISTS artist_genres CASCADE;
DROP TABLE IF EXISTS venue_artists CASCADE;
DROP TABLE IF EXISTS venue_genres CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS artists CASCADE;
DROP TABLE IF EXISTS venues CASCADE;
DROP TABLE IF EXISTS genres CASCADE;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';
