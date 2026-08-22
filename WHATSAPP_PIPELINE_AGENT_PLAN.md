# WhatsApp Pipeline — Agent Delegation Plan (remaining work)

Companion to `WHATSAPP_PIPELINE_REVIEW.md` (the audit) and `WHATSAPP_PIPELINE_STEPS_3_TO_7.md` (the spec). **This file is the work-assignment plan.** It says what is done, what is left, who does which part, and the exact file boundaries that keep agents from colliding.

Read §1 and §2 before assigning anything.

---

## 1. Current state

### 1.1 Committed
`8ac387b feat(backend): single-writer WhatsApp pipeline, P0 fixes, batch failure handling`

Contains steps **1**, **2**, and **3B** (including the bisect-termination fix). 54 files. Verified self-consistent by building a throwaway worktree from it: imports clean, tests green.

### 1.2 Uncommitted in the working tree (verified, **213 passed**)
| Module | State |
|---|---|
`backend/app/services/temporal_parser.py` | `DatePrecision` + `resolve()` added, `parse_date_time()` retained. 4 bugs fixed post-delivery. |
`backend/tests/fixtures/temporal_cases.py` | ~170 cases. Contradictory fixtures reconciled. |
`backend/tests/unit/test_temporal_parser.py` | passing |
`backend/app/services/urgency_service.py` | `compute_urgency` + `recompute_for_user`. ALERT-floor ordering bug fixed. |
`backend/tests/unit/test_urgency_service.py` | passing |
`backend/app/services/prefilter.py` | `classify_skip`, `compute_text_hash`, `normalise_for_hash`. Self-match + duplicated-hash bugs fixed. |
`backend/app/models.py` | `RawMessage.text_hash` added |
`backend/alembic/versions/0006_raw_message_text_hash.py` | new |
`backend/app/startup_migrations.py` | `text_hash` mirrored into the existing raw_messages block |
`backend/app/services/whatsapp_listener_service.py` | `ingest_message` sets `text_hash` via the shared helper |
`backend/tests/unit/test_prefilter.py` | passing, incl. self-match regression |

**Commit this before assigning worktree agents.** See §2.1.

### 1.3 CRITICAL — three modules are inert
They exist, are tested, and **are not called by anything**:

- `prefilter.classify_skip` — not called by `process_message_batch`
- `urgency_service.compute_urgency` — not called anywhere
- `TemporalParser.resolve` — not called by `_wrap_batch_result`

Wiring them is Wave 2 work. Until then the pipeline behaves exactly as it did at `8ac387b`. Do not report these as delivered features.

### 1.4 Conventions already decided — do not relitigate
- **Bare-hour rule**: an hour with no am/pm in **1–7** resolves to PM; 8–12 as written. `BARE_HOUR_PM_RANGE` in `temporal_parser.py`.
- **`next <weekday>` = the COMING weekday**, identical to `this <weekday>` and to the bare form. This diverges from the original spec on purpose: for a deadline app the error is asymmetric — resolving early gives a harmless early reminder, resolving late means a missed deadline. `next week` as a standalone span still means Monday of the following week.
- **Multi-date tie-break**: rightmost mention wins (`date_candidates` sorted by position, descending).
- **Batch failure**: retry via the dispatch cycle using `ai_attempts`; bisect after 3; quarantine a singleton at max. The `ai_attempts` ceiling is applied to auto-select and the dispatcher **only**, never to the explicit `message_ids` path.

---

## 2. Lessons from the first fan-out — read this or repeat the mistakes

### 2.1 Agent Manager cuts worktrees from the DEFAULT BASE BRANCH, not current HEAD
Three worktrees were created from `23ecd0b` even though `8ac387b` was committed and verified beforehand. The agents got a tree with no `process_message_batch`, no `ai_attempts`, and missing migrations `0004`/`0005`, so one of them wrote a migration whose `down_revision` did not exist in its own worktree.

**Mitigations, in order of preference:**
1. Ensure the base branch actually contains the prerequisite commits before launching.
2. Scope each agent to **net-new files only**, so a stale base cannot matter.
3. If neither is possible, use `local` mode — but then patch `backend/tests/conftest.py:12` first, because `TEST_DATABASE_URL = "sqlite:///./test_knowtis.db"` is a hardcoded shared file and concurrent `pytest` runs corrupt each other.

Always verify with `git -C <worktree> log --oneline -1` immediately after launch.

### 2.2 Agents may return idle having written nothing
Two of three finished their first turn with `additions: 0`. A second, more imperative prompt ("open file X, edit it, create file Y, run this command") produced full output. **Check `git.additions` in `agent_manager` `action: "list"` before assuming a task is done.**

### 2.3 All three shipped bugs their own tests missed
- urgency: ALERT floor applied before confidence scaling, so `0.75 × 0.85 = 0.638`. Its own test asserted `>= 0.75` — it never ran it.
- prefilter: no self-exclusion on the repeat check, so once wired it would have skipped **100% of traffic**. Its tests passed only because they never modelled the real call site.
- temporal: 4 of its own fixtures failed, and two more were mutually contradictory (`next Mon` vs `next Monday`, `next Friday` vs `next Monday`).

**Never merge an agent's branch on its own report.** Run the suite yourself, read the diff, and specifically ask "does any test model the real call site?"

### 2.4 Tell agents to leave the test DB alone
All three left `backend/test_knowtis.db` dirty. Add "run `git checkout -- backend/test_knowtis.db` before finishing" to every backend prompt.

---

## 3. Why the remaining work is mostly sequential

The rest of the backend converges on three files — `tasks.py`, `event_extraction_service.py`, `agnes_service.py`. 3C, 4A, 4C, prefilter wiring and urgency wiring all edit them. Splitting those across agents produces conflicting rewrites of the same functions, and merging costs more than doing them in order.

Genuine parallelism exists in exactly two places: **the schema layer** and **the frontend**.

```
WAVE 1  (parallel)
  Agent SCHEMA   -> step 5: migration, models, dedup rewrite, search
  Agent FRONTEND -> step 7 UI, defensive against fields not yet served

WAVE 2  (sequential, single owner — the lead)
  3C  index reconciliation + per-message anchor
  4A  date_expression prompt + wire TemporalParser.resolve
      wire prefilter into process_message_batch
      wire urgency into the writer
  4C  delete the dead classifier stack
  4E  rewrite test_classifier.py
  3A  triggers + per-group dispatch lock

WAVE 3  (after Wave 1 lands)
  Agent API -> step 7 backend surface: group_name, PUT /events/{id}, training feedback by event id
```

---

## 4. Wave 1 — Agent SCHEMA

**Model:** `kat-coder-pro-v2.5` (variant `high`) — broad, mechanical, multi-file, well-specified. It was the best-behaved agent in the first round.

**Owns exclusively:**
```
backend/app/models.py
backend/alembic/versions/0007_pipeline_schema.py        (new)
backend/app/startup_migrations.py
backend/app/services/deduplication_service.py
backend/app/services/search_service.py
backend/tests/unit/test_deduplication.py                (new)
```

**Must NOT touch:** `tasks.py`, `event_extraction_service.py`, `agnes_service.py`, `schemas.py`, `classifier_service.py`, `temporal_parser.py`, `prefilter.py`, `urgency_service.py`, anything under `frontend/`.

### Prompt

> Implement step 5 of the WhatsApp pipeline rework: the schema migration and the deduplication rewrite.
>
> Read `WHATSAPP_PIPELINE_STEPS_3_TO_7.md` section 5 first, plus section 0 for ground rules and section 1.3 for the current schema. Read `WHATSAPP_PIPELINE_AGENT_PLAN.md` section 1.4 for conventions already decided. Do not re-audit the codebase — the findings in those documents are verified.
>
> STRICT FILE SCOPE — touch only: `backend/app/models.py`, `backend/alembic/versions/0007_pipeline_schema.py` (new), `backend/app/startup_migrations.py`, `backend/app/services/deduplication_service.py`, `backend/app/services/search_service.py`, `backend/tests/unit/test_deduplication.py` (new). Do NOT touch `tasks.py`, `event_extraction_service.py`, `agnes_service.py`, `schemas.py`, `classifier_service.py`, or anything under `frontend/` — another agent and the lead own those.
>
> PART 1 — columns on `academic_events`: `status` (ACTIVE / CANCELLED / SUPERSEDED, default ACTIVE, indexed), `superseded_by_id` (uuid FK to academic_events.id, ON DELETE SET NULL), `date_precision` (EXACT / DAY_ONLY / UNKNOWN, default UNKNOWN), `source_raw_message_id` (uuid FK to raw_messages.id, ON DELETE SET NULL, indexed), `event_index` (int default 0), `revisions` (JSONB on PostgreSQL, JSON on SQLite, default empty list). Keep the existing `source_message_id` String column — do not drop it, backfill `source_raw_message_id` from it where a row matches.
>
> PART 2 — constraints: `UNIQUE (user_id, source_raw_message_id, event_index)` and an index on `(user_id, course_code, event_type, date_time)`. In PostgreSQL NULLs do not collide in a unique constraint, so existing rows and manually-created events are unaffected — that is intended, note it in the migration docstring.
>
> PART 3 — pgvector. Do NOT change the type of the existing `embedding` column in place; it currently holds JSON strings and an in-place change risks the table. Add a parallel `embedding_vec Vector(384)` column, guarded on `bind.dialect.name == "postgresql"` because the test suite runs on SQLite. Create the HNSW index (`vector_cosine_ops`) only on PostgreSQL. Leave a clearly-marked TODO for the backfill job and the eventual drop of the old column — do not write the backfill.
>
> PART 4 — rewrite `find_duplicate`: business key first, vectors second. If `course_code`, `event_type` and `date_time` are all present, look up `(user_id, course_code, event_type, date(date_time))` using the new index and return on a hit. Only fall through to vector similarity when the business key is incomplete. Raise the similarity threshold from 0.88 to **0.92** — at 0.88 with `canonical_dedup_text` there is a real risk of merging "CSC301 Assignment 1" with "CSC301 Assignment 2". Delete the Python `for event in recent_events` cosine loop and use pgvector on PostgreSQL, keeping a dialect-selected Python fallback so SQLite tests still work.
>
> PART 5 — `reconcile_event`. Replace `target.title = f"[CANCELLED] {target.title}"` with `status = CANCELLED`: a title prefix is not queryable and poisons the next dedup pass. Cancel that event's pending reminders. On UPDATE, append an entry to `revisions` recording what changed instead of concatenating into `description`. Fix the targeting bug: it currently takes `matching_events[0]`, the newest row for that course, with no event_type filter, no date proximity and no title similarity — target by `(course_code, event_type, nearest date_time within ±7 days)` instead.
>
> Every schema change must exist in BOTH the Alembic version and the `startup_migrations.py` mirror, and that file branches on SQLite vs PostgreSQL — handle both. Follow the pattern already used there for `ai_attempts` and `text_hash`.
>
> Tests: cover the business-key hit, the vector fallback, that "Assignment 1" and "Assignment 2" do NOT merge, that cancellation sets status and leaves the title clean, and that UPDATE targets by type and date proximity rather than recency.
>
> Verify from the `backend` directory: `python -m pytest tests -q --no-header` (baseline **213 passed**, finish at 213 + your new tests, 0 failures) and `python -c "import app.main, app.tasks, app.scheduler, app.celery_app"`. Run `git checkout -- backend/test_knowtis.db` before finishing. Do not commit, do not push. Report the final test count and any spec ambiguity and how you resolved it.

---

## 5. Wave 1 — Agent FRONTEND

**Model:** `DeepSeek-V4-Pro` (variant `high`) — UI judgement plus a lot of files.

**Owns exclusively:** everything under `frontend/src/`. Nothing in `backend/`.

**Key constraint:** the backend does not serve `group_name`, `status`, `date_precision` or `needs_review` on events yet — Wave 3 adds them. Every new field must be read **optionally**, so the UI degrades gracefully today and lights up when the API catches up.

### Prompt

> Implement step 7 of the WhatsApp pipeline rework, frontend only: source provenance and the correction loop.
>
> Read `WHATSAPP_PIPELINE_STEPS_3_TO_7.md` section 7, section 4 (frontend gaps), and section 0 for ground rules. Also read `AGENTS.md` — this is primarily a native Android/iOS app via Capacitor.
>
> HARD CONSTRAINTS: the frontend is a static export (`frontend/next.config.ts` sets `output: "export"`), so there are NO API routes and NO server actions — data flows client → Zustand store → axios → FastAPI. Use `@capacitor/local-notifications` and `@capacitor/push-notifications` only; never `Notification.requestPermission()`, `new Notification()`, or Web Push service workers. Every interactive element needs a minimum 48×48 px touch target. Preserve safe-area insets and the floating `BottomNav`.
>
> STRICT FILE SCOPE — only files under `frontend/src/`. Do NOT touch anything in `backend/` — the lead and another agent own the backend.
>
> IMPORTANT: the backend does not yet serve `group_name`, `status`, `date_precision` or `needs_review` on events. Treat all of them as OPTIONAL. The UI must render correctly today when they are absent and automatically light up once the API serves them. Do not block on the backend and do not fake the data.
>
> PART 1 — types. `frontend/src/lib/events.ts` currently declares only `id, event_type, course_code?, title, description?, venue?, date_time?, urgency_score, confidence_score, relevance_score?, actionability_score?, is_duplicate, created_at`. Add optional `group_id`, `group_name`, `source_group_jid`, `needs_review`, `status`, `date_precision`.
>
> PART 2 — provenance. Nothing in the UI currently shows where an event came from, even though the dashboard section is titled "Latest from Groups" and names no group. Show the group name on: the `StickyNote` cascade cards, the "Latest from Groups" rows, `EventDetailModal`, and the `/updates` cards. `EventDetailModal` currently reads "Extracted {created_at}" — change it to name the source, e.g. "From {group_name} · {created_at}", falling back to the current text when `group_name` is missing.
>
> PART 3 — respect `date_precision`. A `DAY_ONLY` event must render as "Friday", never "Friday 9:00 AM". Fabricated precision is worse than admitting the time is unknown. When `date_precision` is absent, keep current behaviour.
>
> PART 4 — the confirm chip. Add a `trainingApi` to `frontend/src/lib/api.ts` (it does not exist) with `submitFeedback(eventId, feedbackType, corrections?)` and `updateEvent(id, patch)`. `feedbackType` is one of `confirmed_correct`, `corrected`, `reported_noise`. On any card where `needs_review === true`, show a "Looks right?" chip with confirm / reject / edit. Confirm and reject should update the store optimistically and roll back on failure. Reject means `reported_noise` and archives locally. Edit opens a small form limited to title, course code, date/time and venue.
>
> PART 5 — truncation signal. The events endpoint caps free-tier users at 3 items while the dashboard asks for 24, with no indication. When the response reports a total greater than the returned count, render something like "Showing 3 of 12 — upgrade to see all". Read the count defensively; the field may not exist yet.
>
> Note `deleteEvent` is currently only reachable from `/events`, which is not in `frontend/src/components/layout/bottom-nav.tsx`. Make archive reachable from the dashboard and `/updates` cards.
>
> Verify: `cd frontend && npx tsc --noEmit` must be clean, and `npm run build` must succeed. Do not commit, do not push. Report which fields you made optional, and every place you added a fallback for a field the backend does not serve yet.

---

## 6. Wave 2 — the lead, sequential (do NOT delegate)

One owner, one commit per bullet. These all edit the same three files, so parallelising them creates conflicting rewrites of the same functions.

**Files:** `tasks.py`, `event_extraction_service.py`, `agnes_service.py`, `schemas.py`, `classifier_service.py`, `celery_app.py`, `config.py`, `tests/unit/test_classifier.py`.

1. **3C — index reconciliation.** `_parse_batch_json` already carries `"index"`; `extract_batch_via_agnes` drops it and the writer attributes every event to `unprocessed[0]`. Stamp `_source_index` on each wrapped event, build `{i+1: raw}` in the writer, validate range / duplicates / omissions with a warning and fall back to the batch head. Strip `_source_index` before it reaches the ORM. Also thread a **per-message anchor** — the batch currently uses `unprocessed[0].created_at` for all 15 messages, so a batch crossing midnight resolves "tomorrow" wrongly.
2. **4A — `date_expression`.** Change both Agnes prompts to return `date_expression` + `date_is_explicit` instead of `date_time`, and to stop emitting `urgency_score`. Update `ExtractedEventItem`, keeping `date_time` accepted-but-ignored for one release with a log line. Wire `TemporalParser.resolve` into `_wrap_batch_result` and return `date_precision`.
3. **Wire the prefilter.** Call `classify_skip` at the top of `process_message_batch`, passing `exclude_message_id=msg.id` — **without it every message self-matches and the prefilter drops 100% of traffic**. Mark skips with their `SKIPPED_*` status and `ai_processed = True`, and send only survivors to Agnes.
4. **Wire urgency.** Call `compute_urgency` on create and on reconcile, and add `recompute_for_user` to the existing 5-minute reminder job in `scheduler.py`.
5. **4C — delete the dead stack.** `semantic_classifier.py` (whole file, plus any `prewarm()` call in `main.py`), `setfit_classifier_service.py` (move under `backend/training/` or delete), and from `event_extraction_service.py`: `extract_event`, `extract_events`, `_extract_legacy`, `_is_peer_question_or_non_event`, `_is_bare_fragment`, `_assess_actionability`, `_event_completeness`, `_extract_via_llm`. From `classifier_service.py`: `classify_message`, `classify_local_category`, `classify_single_shot`, `classify_event_type`, `calculate_scores`, all `_RE_*` matchers and the keyword machinery. Keep the enums, `CATEGORY_MAP`, `LOCAL_CATEGORY_TO_CLASSIFIER`, `category_to_classifier`. Two latent substring bugs (`"test"` in `"latest"`, `"exam"` in `"example"`) die with this and need no separate fix.
6. **4E — rewrite `tests/unit/test_classifier.py`.** It tests the functions step 5 deletes. Port the intent: signal/noise → prefilter and Agnes-mocked pipeline tests; fragments → `SKIPPED_FRAGMENT`; temporal → the existing fixture corpus. **This is the largest hidden cost in the whole plan.**
7. **3A — triggers.** Drop the beat to 30 s so an "age > 90 s" trigger can actually fire, move the decision into the dispatcher (size ≥ 15 / age > 90 s / tripwire keyword), and use portable SQL for the tripwire because SQLite has no `ILIKE`. **Add a per-group dispatch lock** — at 30 s a still-running batch gets dispatched again and two workers process the same rows. Reuse the `_acquire_scheduler_lock` pattern. The lock must NOT block bisect children: 3B enqueues two jobs for the same group, so exempt the explicit `message_ids` path or key the lock on a hash of the id set.

---

## 7. Wave 3 — Agent API (after Wave 1 SCHEMA lands)

**Model:** `Qwen3.8-27B` (variant `high`) — small, well-bounded surface.

**Owns exclusively:**
```
backend/app/routes/events_routes.py
backend/app/routes/training_routes.py
backend/app/schemas.py          (response models only)
backend/tests/integration/test_events_routes.py
backend/tests/integration/test_training_feedback.py   (new)
```

### Prompt

> Implement the step 7 backend surface that the frontend consumes.
>
> Read `WHATSAPP_PIPELINE_STEPS_3_TO_7.md` sections 7A, 7B, 7C, plus section 0.
>
> STRICT FILE SCOPE — only `backend/app/routes/events_routes.py`, `backend/app/routes/training_routes.py`, `backend/app/schemas.py`, and the two test files named above. Do NOT touch `models.py`, `tasks.py`, `event_extraction_service.py`, `deduplication_service.py`, or anything under `frontend/`.
>
> 1. Add `group_name` to the event response via a join or a lightweight subquery — do NOT N+1 per event. Also expose `status`, `date_precision`, `needs_review`, `group_id` and `source_group_jid`, all of which now exist on the model.
> 2. Filter out `status == SUPERSEDED` in the list endpoint, keeping the existing `is_archived == False` and `is_duplicate == False` filters.
> 3. Add `PUT /api/v1/events/{id}`. It does not exist anywhere, which makes the `corrected` feedback type unusable. Restrict the patch to `title`, `course_code`, `date_time`, `venue`, `event_type`. It must set `needs_review = False` and append an entry to `revisions`.
> 4. `POST /api/v1/training/feedback` currently keys on `prediction_id`, but the client only has an event id. Accept `academic_event_id` and resolve the `PredictionRecord` through its `academic_event_id` column, or add `GET /training/predictions?academic_event_id=`. On `confirmed_correct`, clear `needs_review` on the **AcademicEvent**, not only on the PredictionRecord.
> 5. The list endpoint caps free-tier users at 3 items with no signal to the client. Return an accurate `total` plus either `truncated: bool` or `plan_limit: int` so the UI can say "Showing 3 of 12".
>
> Verify from `backend`: `python -m pytest tests -q --no-header` with 0 failures, and `python -c "import app.main"`. Run `git checkout -- backend/test_knowtis.db` before finishing. Do not commit or push. Report the response shape you settled on, field by field, so the frontend agent can align.

---

## 8. Integration protocol

1. **Never merge on an agent's report.** Read the diff, then run the suite yourself in the main tree.
2. **Integrate by copying files, not by merging branches**, while the base-branch problem in §2.1 persists. It is more predictable and it forces you to read what you take.
3. **For every agent test suite, ask: does any test model the real call site?** That single question would have caught the prefilter self-match bug and the urgency ALERT-floor bug.
4. After each integration: full suite, then `python -c "import app.main, app.tasks, app.scheduler, app.celery_app"`.
5. Any schema change must land in **both** `alembic/versions/` and `startup_migrations.py`.
6. Remove the matching `TODO(step-N)` marker when a step lands; renumber it if it must survive.

---

## 9. Definition of done

- [ ] `prefilter`, `urgency_service` and `TemporalParser.resolve` are all actually called by the pipeline (§1.3)
- [ ] One writer to `academic_events`, and reprocessing a message creates no second row
- [ ] Cancellations set `status = CANCELLED` and cancel pending reminders
- [ ] Dashboard ordering is deadline-driven, not keyword-driven
- [ ] No code path fabricates 09:00; `DAY_ONLY` renders without a time
- [ ] Every card names its source group
- [ ] `needs_review` cards offer confirm / reject / edit, and confirming writes a `TrainingFeedback` row
- [ ] Truncated lists say so
- [ ] `semantic_classifier.py`, `setfit_classifier_service.py` and the legacy extractor are gone
- [ ] Full suite green; `startup_migrations.py` mirrors every migration
- [ ] No Web Notification / Web Push API anywhere in the frontend
