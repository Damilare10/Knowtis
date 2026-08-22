#!/bin/bash

# The web container only runs the HTTP API. Background jobs belong in the
# worker/beat containers so a VPS restart does not duplicate schedulers.
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
