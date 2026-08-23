# WhatsApp Pipeline — Handoff

**Read this file before `WHATSAPP_PIPELINE_AGENT_PLAN.md`.** The plan's §1 ("Current state") is now stale: it describes the tree as it was before Wave 2. Where the two disagree, this file wins. The plan is still correct and authoritative for the *prompts* and the *file-ownership boundaries* in §4, §5 and §7, with the amendments in §4 below.

---

## 1. State of the tree

| Commit | Contents |
|---|---|
| `8ac387b` | Steps 1, 2, 3B — single writer, P0 fixes, batch failure handling (bisect/quarantine) |
| `e5db5a9` | Steps 4B, 4D, 6 — `TemporalParser.resolve`, `urgency_service`, `prefilter`. Built and tested, **inert** at that commit. |
| **uncommitted** | **All of Wave 2.** Not yet committed. |

**Test baseline: `246 passed`** (was 213 at `e5db5a9`).

```
cd backend
python -m pytest tests -q --no-header
python -c "import app.main, app.tasks, app.scheduler, app.celery_app"
git checkout -- test_knowtis.db
```

### 1.1 COMMIT WAVE 2 BEFORE LAUNCHING ANY WORKTREE AGENT

Agent Manager cuts worktrees from the **default base branch, not current HEAD** (plan §2.1). Wave 2 is uncommitted, so an agent launched now gets a tree with the old `classifier_service.py`, the deleted `semantic_classifier.py` still present, `calculate_scores` still live in `events_routes.py`, and a 213-test baseline. That is exactly how the first fan-out produced a migration whose `down_revision` did not exist.

Commit first. Then `git -C <worktree> log --oneline -1` immediately after launch to confirm the base.

---

## 2. Wave 2 — DONE (uncommitted)

All seven bullets of plan §6. The three previously-inert modules are now genuinely called by the pipeline.

**Wiring (items 1–4)**
- Prefilter is called at the top of `process_message_batch` with **both** `exclude_message_id=msg.id` and `before=msg.created_at`. Both are required: id-exclusion alone makes two identical messages in one batch exclude *each other*, so both are dropped and the announcement is lost.
- `_source_index` is stamped by `extract_batch_via_agnes` and consumed by the writer, which validates range/duplicates/omissions and strips the key before the ORM. Per-message anchors thread through, so a batch crossing midnight resolves "tomorrow" per message rather than per batch head.
- Agnes prompts (single + batch) return `date_expression` + `date_is_explicit`, never a resolved date and never `urgency_score`. `TemporalParser.resolve` does the arithmetic in `_wrap_batch_result`.
- `compute_urgency` runs on create and on reconcile. `scheduler.run_reminder_cycle()` refreshes urgency then fires reminders; both the APScheduler job and the Celery beat task call it, so the two drivers cannot drift.

**4C — dead stack deleted**
- `semantic_classifier.py` deleted; `prewarm()` call removed from `main.py`; `semantic_prewarm_enabled` removed from `config.py`.
- `setfit_classifier_service.py` **moved to `backend/training/`**, not deleted — `model_verification_service.py` → `ci_gate_service.py` still uses it for the CI model gate. Its import was updated to `from training.setfit_classifier_service import ...`.
- `event_extraction_service.py`: 601 → 254 lines. Surviving methods: `extract_batch_via_agnes`, `_wrap_batch_result`, `canonical_dedup_text`, `align_course_code`. No longer imports `NERService`, `ConfidenceScorer` or `LLMService`.
- `classifier_service.py`: 389 → 80 lines, taxonomy only (`Classification`, `EventCategory`, `ClassifierCategory`, `LOCAL_CATEGORY_TO_CLASSIFIER`, `CATEGORY_MAP`, `MessageClassifier.category_to_classifier`).

**4E — `test_classifier.py` rewritten** (24 → 20 tests, every intent ported, see §5).

**3A — triggers + lock**
- Beat 2 min → **30 s**. An "age > 90 s" trigger cannot fire on a 2-minute beat.
- Dispatcher decides: size ≥ `batch_size_trigger` / age > `batch_age_trigger_seconds` / tripwire keyword. One aggregate `GROUP BY` pass, not a query per group. Tripwire uses `func.lower(col).like(...)` because **SQLite has no `ILIKE`**.
- Per-group dispatch lock, same atomic `O_CREAT|O_EXCL` + staleness pattern as `_acquire_scheduler_lock`. Taken by the dispatcher, released by the task in `finally` (including on exception). The explicit `message_ids` path never touches it, so 3B's two bisect children cannot deadlock each other.
- New config: `batch_size_trigger` (15), `batch_age_trigger_seconds` (90), `batch_tripwire_keywords`, `batch_dispatch_lock_seconds` (600). Added to **both** the class body and the `__init__` mirror in `config.py`.

### 2.1 Two deviations from the plan, and why

**`calculate_scores` was not dead.** Plan §6 bullet 5 lists it for deletion, but it had two live production callers: `events_routes.py:179` (manual event creation) and `ocr_routes.py:264` (OCR extraction). Deleting it blind would have 500'd both endpoints. Both were converted to `compute_urgency`; manual events take confidence/relevance/actionability = 1.0 (the user typed the fields), OCR reuses its own hoisted `extraction_confidence`. This also closes the DoD item "dashboard ordering is deadline-driven, not keyword-driven" — those were the last two keyword-urgency writers in the codebase.

**`setfit_classifier_service.py` was not dead** — see 4C above. Moved rather than deleted, which is the plan's own stated alternative.

---

## 3. What remains

```
WAVE 1 (parallel, after Wave 2 is committed)
  Agent SCHEMA    -> step 5: migration 0007, models.py, startup_migrations.py,
                     deduplication_service.py, search_service.py
  Agent FRONTEND  -> step 7 UI, defensive against fields not yet served

WAVE 2.5 (lead, sequential, AFTER SCHEMA lands)  <-- NEW, see §4.3
  writer populates source_raw_message_id + event_index
  reconcile CANCEL -> status, and drop the _urgency_view shim

WAVE 3 (after Wave 1 SCHEMA lands)
  Agent API       -> step 7 backend surface
```

Prompts are in plan §4 (SCHEMA), §5 (FRONTEND), §7 (API). **Apply the amendments in §4 below before pasting them.**

---

## 4. Amendments to the plan's agent prompts

### 4.1 Agent SCHEMA — add these to the prompt

**`date_precision` column values must be lowercase.** `DatePrecision` in `temporal_parser.py` is `EXACT = "exact"`, `DAY_ONLY = "day_only"`, `UNKNOWN = "unknown"`, and `_wrap_batch_result` already returns `date_precision.value`, i.e. the lowercase string. A column declared as `sa.Enum("EXACT", "DAY_ONLY", "UNKNOWN")` will be rejected by PostgreSQL the first time the writer assigns `"day_only"`. Use the lowercase values (or `values_callable`) so the column matches the enum that already exists. SQLite will not catch this — it does not enforce enum values — so it will pass the test suite and fail in production.

**`reconcile_event` must stay tolerant of extra keys.** `event_data` now carries `date_precision`, which has no ORM column until this step. The current implementation only ever reads via `event_data.get(...)`, never `AcademicEvent(**event_data)`. Keep it that way.

**Do not touch `tasks.py`.** Populating the new `source_raw_message_id` / `event_index` columns is Wave 2.5 (lead), because `tasks.py` is the lead's file. Ship the columns and the constraint; the writer follow-up is tracked in §4.3.

### 4.2 Agent FRONTEND — add these to the prompt

`date_precision` arrives as one of the lowercase strings `"exact"`, `"day_only"`, `"unknown"`. Compare against those exact values. The PART 3 rule (a `DAY_ONLY` event renders as "Friday", never "Friday 9:00 AM") keys on `"day_only"`.

Everything else in plan §5 stands unchanged.

### 4.3 Wave 2.5 — lead, after SCHEMA lands (NEW)

The plan's DoD says "reprocessing a message creates no second row", enforced by `UNIQUE (user_id, source_raw_message_id, event_index)`. **That constraint does nothing until the writer populates those columns.** In PostgreSQL, NULLs do not collide, so every row written today has `source_raw_message_id = NULL` and the constraint never fires.

After SCHEMA lands, in `tasks.py`:
1. Set `source_raw_message_id=src_raw.id` on create (the existing `source_message_id` keeps the WhatsApp string id — do not conflate them).
2. Set `event_index` per source message: 0, 1, 2… for multiple events extracted from the same message. `extract_batch_via_agnes` can return several events with the same `_source_index`, so index them within that group, not across the batch.
3. Persist `date_precision` on the row, then delete the `_urgency_view` shim at `tasks.py:76` and score the instance directly. Marked `TODO(step-5)`.
4. Handle the unique-constraint violation on reprocess (catch `IntegrityError`, treat as already-written).
5. `deduplication_service.reconcile_event` CANCEL branch currently writes a `[CANCELLED]` title prefix; once `status` exists, SCHEMA replaces that. Verify `compute_urgency` then returns 0.0 for cancelled events — it already reads `status` via `getattr`, so it starts working automatically.

### 4.4 Agent API (Wave 3) — add these to the prompt

`events_routes.py` **no longer imports `MessageClassifier`**; it imports `compute_urgency` from `app.services.urgency_service`. Do not reintroduce keyword scoring, and do not re-add `calculate_scores` — it no longer exists. `create_event` sets confidence/relevance/actionability to 1.0 and derives `urgency_score` via `compute_urgency(event)`; preserve that.

Everything else in plan §7 stands unchanged.

---

## 5. Where the old test coverage went

`test_classifier.py` was rewritten, so anyone looking for a deleted assertion should look here:

| Original | Now |
|---|---|
| `classify_message` signal/noise | Agnes's job — `test_batch_extraction_wiring.py` (NOISE items yield no events), `test_pipeline_integration.py` (survivors reach extraction) |
| `classify_event_type` | Agnes's job, same files |
| `classify_local_category` | deleted — nothing classifies locally any more |
| `TestEventExtractionBareFragment` (10 cases) | `test_classifier.py` — prefilter `SKIPPED_FRAGMENT` / pass-through, parametrized |
| `calculate_scores` bounds | `test_classifier.py` — derived-urgency range + "urgency ignores the word urgent". Depth in `test_urgency_service.py` |
| `extract_events` multi-event | `test_batch_extraction_wiring.py::test_one_message_can_yield_multiple_events` |
| temporal resolution | `tests/fixtures/temporal_cases.py` (~170 cases) via `test_temporal_parser.py` |
| taxonomy / schemas / anchor / course codes | kept in `test_classifier.py` |

New test files:
```
backend/tests/unit/test_pipeline_integration.py     12 tests — prefilter/index/urgency wiring in the writer
backend/tests/unit/test_batch_extraction_wiring.py  12 tests — _wrap_batch_result, per-message anchor, 4A
backend/tests/unit/test_dispatch_triggers.py        13 tests — 3A triggers + lock
```

`test_batch_extraction_wiring.py` exists because **every** pre-existing test mocked `extract_batch_via_agnes` wholesale, so nothing under it ran. It mocks only the HTTP boundary (`AgnesService.classify_and_extract_batch`) so the real wrapping path executes.

---

## 6. Open TODOs in the tree

| Marker | Location | Meaning |
|---|---|---|
| `TODO(step-5)` | `tasks.py:76` | Drop the `_urgency_view` shim once `date_precision`/`status` columns exist. See §4.3. |
| `TODO(step-3)` | `tasks.py:494` | The dispatch lock is a per-host file lock. A multi-host worker deployment needs a Redis `SET NX EX` lock; the 30 s duplicate-dispatch problem is solved on one host only. |

---

## 7. Conventions already decided — do not relitigate

- **Bare-hour rule**: an hour with no am/pm in 1–7 resolves to PM; 8–12 as written (`BARE_HOUR_PM_RANGE`).
- **`next <weekday>` = the COMING weekday**, identical to `this <weekday>` and the bare form. Deliberate divergence from the original spec: for a deadline app the error is asymmetric — early is a harmless early reminder, late is a missed deadline. `next week` standalone still means Monday of the following week.
- **Multi-date tie-break**: rightmost mention wins.
- **Batch failure**: retry via the dispatch cycle using `ai_attempts`; bisect after 3; quarantine a singleton at max. The ceiling applies to auto-select and the dispatcher only, never to the explicit `message_ids` path.
- **Prefilter recall over precision**: a false pass costs a fraction of a cent; a false skip loses a student's deadline.
- **Urgency is always derived** from time-to-deadline. Never taken from a model, never from keyword presence.
- **Dates are always resolved locally** by `TemporalParser`, never by the LLM. The model returns the phrase as written.

---

## 8. Critical constraints (from AGENTS.md)

- **Capacitor native Android/iOS app.** Frontend is a static export (`output: "export"`) — no Next.js API routes, no server actions. Data flows client → Zustand → axios → FastAPI.
- `@capacitor/push-notifications` + `@capacitor/local-notifications` only. **Never** `Notification.requestPermission()`, `new Notification()`, or Web Push service workers.
- Safe-area insets, 48×48 px minimum touch targets, floating `BottomNav` preserved.
- Any schema change lands in **both** `alembic/versions/` and `startup_migrations.py`, which branches SQLite vs PostgreSQL.

---

## 9. Integration protocol

1. **Never merge on an agent's report.** Read the diff, run the suite yourself in the main tree.
2. **Integrate by copying files, not merging branches**, while the base-branch problem in §1.1 persists.
3. **Check `git.additions` in `agent_manager list`** — two of three agents in the first fan-out returned idle having written nothing.
4. **For every agent test suite ask: "does any test model the real call site?"** That single question would have caught the prefilter self-match (100% traffic drop), the urgency ALERT floor (`0.75 × 0.85 = 0.638`), and the `before=` gap in Wave 2.
5. **Mutation-test any test that passes on the first run** for a claim you care about. Break the line the test targets, confirm the test goes red, revert. Three separate bugs in this project shipped under green tests.
6. `git checkout -- backend/test_knowtis.db` at the end of every backend turn.
7. Remove the matching `TODO(step-N)` marker when a step lands.
8. After each integration: full suite, then `python -c "import app.main, app.tasks, app.scheduler, app.celery_app"`.

---

## 10. Definition of done

- [x] `prefilter`, `urgency_service` and `TemporalParser.resolve` are all actually called by the pipeline
- [x] No code path fabricates 09:00
- [x] Dashboard ordering is deadline-driven, not keyword-driven (all three writers converted)
- [x] `semantic_classifier.py` and the legacy extractor are gone; SetFit is out of the request path
- [ ] One writer to `academic_events`, and reprocessing a message creates no second row ← needs §4.3
- [ ] Cancellations set `status = CANCELLED` and cancel pending reminders ← SCHEMA
- [ ] `DAY_ONLY` renders without a time ← FRONTEND
- [ ] Every card names its source group ← FRONTEND + API
- [ ] `needs_review` cards offer confirm / reject / edit, and confirming writes a `TrainingFeedback` row ← FRONTEND + API
- [ ] Truncated lists say so ← FRONTEND + API
- [x] Full suite green (246); `startup_migrations.py` mirrors every migration so far
- [ ] No Web Notification / Web Push API anywhere in the frontend ← FRONTEND
