-- Enable the pgvector extension on first database initialization.
-- Mounted into the postgres image's /docker-entrypoint-initdb.d/ directory,
-- which only runs when the data volume is empty (fresh start).
CREATE EXTENSION IF NOT EXISTS vector;
