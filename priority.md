alrioght # Backend Features & Functions Priority List

Based on the Product Requirements Document (README.md), here is the extracted list of backend functions and features to build, structured logically for implementation:

## 1. Infrastructure & Authentication (Phase 1)
- [x] **FastAPI Setup**: Initialize the core application, middleware (CORS, slowapi rate limiting), and routing structure.
- [x] **Database Setup**: PostgreSQL with `pgvector` for semantic search, and encrypted storage.
- [x] **Authentication**: Google OAuth and Email/Password authentication.
- [x] **Role Management**: Student and System Admin roles (no Group Admin).

## 2. Queueing & Workers
- [x] **Redis + Worker Setup**: Celery app + task bodies exist (`celery_app.py`, `tasks.py`) but `task_always_eager=True` by default; no real worker process or Redis health-check wired.
  - *Done: `task_always_eager` now defaults to `False` (production) and is env-configurable (`CELERY_TASK_ALWAYS_EAGER`); `celery_app.py` wires Redis broker/backend with startup retry + prefetch=1; Redis health-check at `GET /health/redis` and a `redis` component in `GET /status` (`redis_client.py`, `main.py`); `.env.example` updated with broker/backend/eager vars; `Procfile` + `backend/WORKER.md` document `celery -A app.celery_app worker -l info` (and optional beat/flower). `requirements.txt` already includes `celery`/`redis`/`flower`.*
- [x] **Queue Protection**: slowapi API rate limiting in place (`rate_limit.py`); worker-side randomized delays / burst protection NOT implemented.
  - *Done: `RateLimitedTask` base class + `apply_burst_delay()` utility in `tasks.py` inject randomized jitter (`WORKER_JITTER_MIN/MAX_SECONDS`, skipped in eager mode) before task bodies; applied to `process_incoming_message_task`, `send_pending_reminders_task`, `send_night_brief_task`, and the new `process_pending_joins_task`. The join path in `scheduler.py` also calls `apply_burst_delay()`.*
- [x] **Anti-Ban Protection** *(item lives in §3 but completes the rotation piece referenced here)*: 3-minute join intervals + jitter implemented (`scheduler.py`); session rotation + randomized worker timing now built — see note below.

## 3. WhatsApp Integration ("Paste & Go")
*Note: The WhatsApp bot acts strictly as a passive listener ("watcher"). It only reads incoming group announcements and has no outbound messaging capability (no direct DMs or user alerts sent via WhatsApp).*
- [x] **Invite-Link Validation**: Endpoint to validate WhatsApp group links.
- [x] **Headless Listeners**: Backend proxies to an external `http://localhost:3001` connector service.
  - *Done: `app/services/whatsapp_listener_service.py` implements an async HTTP-polling adapter with graceful fallback / exponential backoff when the connector (`WHATSAPP_CONNECTOR_URL`) is unreachable. A Celery beat task `drive-whatsapp-listener` (`app/tasks.py:drive_listener`) polls active groups for new messages every 2 min; `whatsapp_service.py` exposes the connector contract (health/join/rejoin/messages/is_bot_member).*
- [x] **Anti-Ban Protection**: 3-minute join intervals + jitter implemented (`scheduler.py`); session rotation + randomized worker timing NOT built.
  - *Done: `app/session_rotation.py` rotates worker sessions on a configurable interval (`WHATSAPP_SESSION_ROTATION_INTERVAL_MINUTES`) and randomly picks a worker session per join (`WHATSAPP_WORKER_POOL_SIZE`), with a deterministic virtual-session fallback when no `whatsapp_sessions` rows exist. `scheduler._process_pending_joins()` now applies burst-protection jitter, calls `rotate_sessions(db)`, picks a randomized session via `pick_worker_session_id()`, and forwards it to `WhatsAppService.join_group(session_id=...)`. A new `process_pending_joins_task` exposes the flow to the Celery worker/beat.*
- [x] **Coverage State Tracking**: Track group status (ACTIVE, DEGRADED, PAUSED, RECOVERING).
- [x] **Bot Removal Detection**: Reactive webhook handler exists (`whatsapp_routes.py`) but no self-initiated detection/polling.
  - *Done: `WhatsAppListenerService.detect_bot_removal()` self-polls group membership via the connector and transitions a group to DEGRADED/PAUSED when the bot appears removed; scheduled by the `detect-bot-removal` Celery beat task (`app/tasks.py:detect_bot_removal`, every 2 min).*
- [x] **Recovery Logic**: Deduplication makes re-ingestion idempotent; no reconciliation/backfill job or state transition routine.
  - *Done: `app/services/recovery_service.py` `reconcile_groups()` scans DEGRADED/PAUSED/RECOVERING groups, attempts re-join via the connector, re-ingests missed messages (idempotent through deduplication), and transitions state to ACTIVE/RECOVERING appropriately; scheduled by the `reconcile-groups` Celery beat task (`app/tasks.py:recover_groups`, every 5 min).*

## 4. NLP & AI Intelligence Pipeline
- [x] **Semantic Retrieval Layer**: MiniLM embeddings + pgvector cosine search fully implemented (`utils.py`, `search_service.py`, `events_routes.py:/events/search`). *(Was mislabeled unchecked.)*
- [x] **Message Classification**: Classify incoming text into Assignments, Exams/Quizzes, Timetable Changes, etc.
- [x] **Confidence Scoring**: Assign relevance, confidence, and urgency scores to events.
- [x] **Structured Event Extraction**: Convert raw text into structured academic objects (Course, Date, Venue, etc.).
- [x] **Semantic Deduplication**: Compare new events against existing vectors to collapse duplicates.

## 5. OCR Processing Pipeline
- [x] **PaddleOCR Integration**: Implement on-demand image extraction for tagged messages.
- [x] **Preprocessing**: Use OpenCV for layout and table parsing.
- [x] **Structured Output**: Output structured schedules, not just raw text.
- [x] **Smart OCR Querying**: Parse natural language instructions (e.g., "only 300-level courses") to filter OCR output.

## 6. AI Catch-Up Agent & Retrieval
- [x] **Deterministic Response Engine (Free Tier)**: Implemented in `backend/app/services/ai_agent_service.py` + `backend/app/routes/ai_routes.py`. Rule-based composer queries the semantic search (`search_service.py`), reminders (`reminder_service.py`), notifications (`notification_service.py`) and OCR output; parses intents (date windows, course codes, event types) and returns a structured, cited answer with event-ID citations via `POST /api/v1/ai/query` with no LLM. Free tier enforced through `dependencies.py` + `rate_limit.py` daily quotas (`enforce_ai_quota`).
- [x] **Conversational AI Layer (Premium Tier)**: Implemented in `backend/app/services/llm_service.py` wrapping the Groq chat completions API (async `httpx`, `GROQ_API_KEY` from env). Premium tier grounds the LLM on the deterministic retrieval context via a generated system prompt and returns the conversational answer (with SSE streaming when `stream=true`); free users and missing-key premium requests gracefully fall back to the deterministic engine. Models configurable via `AI_FREE_MODEL` / `AI_PREMIUM_MODEL`.

## 7. Notification & Reminders Engine
- [x] **Night Brief Generation**: Aggregate daily summaries of tomorrow's deadlines and urgent changes.
- [x] **Premium Real-Time Alerts**: `notification_service.py` only writes DB inbox rows; no push/DM/timeline-shift detection.
  - *Done: `notification_service.py` now exposes `dispatch_alert()` (used by the reminder service + scheduler) routing urgent alerts through a pluggable push/DM channel abstraction (`PushChannel`/`WebhookPushChannel`, configured via `PUSH_WEBHOOK_URL`/`PUSH_WEBHOOK_ENABLED`), plus `notify_timeline_shift()` which detects scheduled-time changes beyond `TIMELINE_SHIFT_THRESHOLD_MINUTES` and fires an urgent push alert.*
- [x] **Smart Reminder Generation**: Generate countdowns and priority-based cascade events.

## 8. Integrations & API Features
- [x] **Calendar Synchronization**: Generate endpoints for 1-click sync to Google Calendar / Outlook.
- [x] **Dashboard WebSockets/Realtime Feed**: No WebSocket/SSE endpoint in backend; frontend polls HTTP.
  - *Done: `backend/app/routes/realtime_routes.py` exposes an authenticated WebSocket at `/ws/feed` and an SSE fallback at `/feed/stream`; `backend/app/realtime.py` keeps a per-user connection registry. `notification_service.dispatch` fanned out every DB write to live sockets in addition to inbox rows.*
- [ ] **Cascade Widgets**: Build mobile widgets (Android Jetpack Glance & iOS WidgetKit) and a web dashboard preview component to ambiently surface key deadlines.
- [ ] **Subscription Sync (Future Phase)**: RevenueCat webhooks integration to handle premium upgrades and limits (Deprioritized; app not yet going to the Play Store).

## 9. Rate Limiting & Tier Enforcement
- [x] **API Protection**: Apply `slowapi` rate-limiting to API endpoints.
- [x] **Tiered Limits**: Enforce logic for Free vs. Premium tiers (group limits, OCR limits, AI agent modes).

## 10. DevOps & Deployment
- [x] **Docker Compose**: `docker-compose.yml` (postgres/pgvector, redis, api, worker) with healthchecks + named volume; `Makefile` with `up`/`down`/`logs`/`migrate`/`test`.
- [x] **Backend Dockerfile**: `backend/Dockerfile` (uvicorn `app.main:app:8000`) + `backend/Dockerfile.worker` (Celery) + `backend/.dockerignore`.

## 11. Production Hardening
- [x] Structured logging
- [x] Request-id middleware
- [x] Global exception handler
- [x] OpenAPI polish

## 12. Test Suite
- [x] **Backend Test Harness**: `backend/pytest.ini` + shared `conftest.py` fixtures (test client, auth override, seeded DB); unit tests for classifier/event-extraction/deduplication/reminder services; API tests for events/reminders/notifications/calendar/OCR/billing with external calls mocked offline.
