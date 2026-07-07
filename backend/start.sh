#!/bin/bash

# The Render web service must only run the HTTP API. Celery worker/beat are
# separate services; starting them here exhausts free-tier memory during wakeup.
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
