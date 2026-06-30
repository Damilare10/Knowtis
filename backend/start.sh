#!/bin/bash

# Start Celery worker in the background
celery -A app.celery_app worker -l info &

# Start Celery beat in the background
celery -A app.celery_app beat -l info &

# Start FastAPI application in the foreground
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
