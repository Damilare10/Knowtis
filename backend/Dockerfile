# syntax=docker/dockerfile:1
#
# Knowtis backend — FastAPI image.
# Serves `uvicorn app.main:app` on port 8000.
# Build context is backend/ (see docker-compose.yml at the repo root).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# System build/runtime dependencies:
#   build-essential  — wheels for C extensions
#   libpq-dev        — PostgreSQL client headers (psycopg2)
#   curl             — container healthcheck (GET /health)
#   libglib2.0-0     — opencv-python-headless runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to maximize layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install psycopg2-binary pgvector

# Copy application code.
COPY . .

RUN chmod +x start.sh

EXPOSE 8000

# Liveness probe: the app exposes GET /health -> {"status": "healthy"}.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["./start.sh"]
