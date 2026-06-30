# Dockerfile for PostgreSQL with pgvector extension
# Used by Render.com deployment

FROM pgvector/pgvector:pg16

# Copy initialization script
COPY init-extensions.sql /docker-entrypoint-initdb.d/

# Expose PostgreSQL port
EXPOSE 5432
