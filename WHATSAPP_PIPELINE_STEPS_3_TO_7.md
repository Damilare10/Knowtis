# WhatsApp Pipeline — Implementation Handoff, Steps 3 → 7

Everything remaining after steps 1 and 2. Companion to `WHATSAPP_PIPELINE_REVIEW.md` (the audit); this file is the execution plan.

**Steps 1 and 2 are done and verified.** Do not redo them. Read §0 for the current state, then execute the step you were asked for.

---

## 0. Ground rules

### 0.1 Do not re-explore
Every file path and line number in this document was verified against the working tree. Line numbers drift as you edit — re-locate by symbol name, not by line, but trust that the symbol exists.

### 0.2 Test baseline
```
cd backend
python -m pytest tests -q --no-header
```
Current baseline: **30 passed, 0 failed.** Any step that lands with fewer passing tests than it started with is not done.

Import smoke test after touching workers:
```
cd backend
python -c "import app.tasks, app.scheduler, app.celery_app, app.main; print('OK')"
```

### 0.3 Hard constraints (from `AGENTS.md`)
Knowtis is primarily a **native Android/iOS app via Capacitor**. The frontend is a static export (`frontend/next.config.ts:4` → `output: "export"`), so there are **no Next.js API routes and no server actions**. All data flows client → Zustand → axios → FastAPI.

- Notifications: `@capacitor/push-notifications` and `@capacitor/local-notifications` only. **Never** `Notification.requestPermission()`, `new Notification()`, or Web Push service workers.
- Any UI work: safe-area insets, 48×48 px minimum touch targets, keep the floating `BottomNav`.

### 0.4 Do not
- Do not reintroduce a second writer to `academic_events`. `process_message_batch` is the only one.
- Do not reintroduce keyword-based signal/noise classification. It is being deleted in step 4.
- Do not let the LLM compute dates. Step 4 moves date arithmetic into `TemporalParser`.
- Do not mark a `RawMessage` as `ai_processed = True` on any failure path.
- Do not edit `.kilo/agent-manager.json`.

---

## 1. Current state (post steps 1–2)

### 1.1 Live pipeline
```
WhatsApp connector (HTTP poll)
  └─ tasks.drive_listener                        beat: */2 min
       └─ WhatsAppListenerService.poll_group
            └─ ingest_message                    store-only, no classify, no extract
                 → RawMessage(ai_processed=False, processing_status=PENDING)

  └─ tasks.dispatch_message_batches              beat: */2 min
       └─ tasks.process_message_batch(group_id)  ← THE ONLY WRITER
            ├─ select 15 oldest unprocessed
            ├─ EventExtractionService.extract_batch_via_agnes
            │     None = failed (retry)  |  [] = all noise  |  [..] = events
            ├─ DeduplicationService.reconcile_event  (CREATE/UPDATE/CANCEL/DUPLICATE)
            └─ mark ai_processed=True + processing_status=PROCESSED  (success only)
```

### 1.2 Key symbols
| Symbol | File |
|---|---|
`dispatch_message_batches` | `backend/app/tasks.py` (~300) |
`process_message_batch` | `backend/app/tasks.py` (~352) |
`ingest_message` | `backend/app/services/whatsapp_listener_service.py` (~117) |
`extract_batch_via_agnes` | `backend/app/services/event_extraction_service.py` (~260) |
`_wrap_batch_result` | `backend/app/services/event_extraction_service.py` (~317) |
`canonical_dedup_text` | `backend/app/services/event_extraction_service.py` (~29) |
`_extract_legacy` (DEPRECATED) | `backend/app/services/event_extraction_service.py` (~132) |
`reconcile_event` | `backend/app/services/deduplication_service.py` (~86) |
`find_duplicate` | `backend/app/services/deduplication_service.py` (~19) |
`AgnesService.BATCH_PROMPT` | `backend/app/services/agnes_service.py` (~59) |
`EXTRACTION_SYSTEM_PROMPT` | `backend/app/services/agnes_service.py` (~17) |
`_parse_batch_json` | `backend/app/services/agnes_service.py` (~274) |
`TemporalParser.parse_date_time` | `backend/app/services/temporal_parser.py` (~60) |
`MessageClassifier.calculate_scores` | `backend/app/services/classifier_service.py` (~365) |
`start_scheduler` (3 jobs) | `backend/app/scheduler.py` (~361) |
beat schedule | `backend/app/celery_app.py:41-76` |

### 1.3 Schema now
`academic_events` — `id, user_id, group_id, event_type, course_code, title, description, venue, date_time, reminder_state, urgency_score, confidence_score, relevance_score, actionability_score, needs_review, is_duplicate, canonical_event_id, embedding (String), source_message_id (String255), source_group_jid, is_archived, created_at, updated_at`

`raw_messages` — `id, user_id, group_id, message_id, sender_jid, sender_name, message_text, message_type, has_media, classification, confidence_score, processing_status, quoted_message_id, quoted_message_text, ai_processed, created_at`

`ProcessingStatus` — `PENDING, PROCESSED, FAILED, QUARANTINED, FILTERED_OUT, SKIPPED_EMPTY, SKIPPED_FRAGMENT, SKIPPED_REPEAT`

Latest migration: `backend/alembic/versions/0004_pipeline_p0_correctness.py` (down_revision `0003_add_join_retry_tracking`). `backend/app/startup_migrations.py` mirrors migrations for the non-Alembic boot path — **update both**.

### 1.4 Open `TODO(step-3)` markers
- `backend/app/celery_app.py:71` — fixed interval instead of real triggers
- `backend/app/tasks.py` (~308) — same, in the dispatcher docstring
- `backend/app/tasks.py` (~473) — every event attributed to `unprocessed[0]`

---

## 2. Dependency graph

```
3C (index reconciliation) ──┬──> 5 (schema: unique constraint)
                            └──> 7a (provenance UI)
3B (failure handling)  ─────────> (closes stall risk introduced by step 1)
3A (triggers)          ─────────> (latency)

4 (temporal + prompt + deletions) ──> 6 (derived urgency)
5 (schema)                        ──> 6 (status filter), 7 (status/precision in UI)
6 (derived urgency)               ──> 7 (correct ordering behind the UI)
```

**Recommended order: 3B → 3C → 4 → 3A → 5 → 6 → 7.**

Rationale: 3B closes a correctness regression introduced by step 1 and should not wait. 3C is small and unblocks two later steps. Step 4 is the first visible quality win and is independent. 3A can slot in any time after 3B. Steps 5–7 are sequential.

---

## 3. STEP 3 — Batch triggers, failure handling, index reconciliation

Three independent workstreams. Do them as separate commits.

### 3B. Failure handling (do this first)

> **STATUS: DONE.** Implemented and reviewed. `RawMessage.ai_attempts` + migration `0005_raw_message_ai_attempts.py` + `startup_migrations.py` mirror, `message_ids` parameter, attempt increment, bisect, quarantine, reset-on-success, and selector/dispatcher filters are all in place. Tests in `backend/tests/unit/test_batch_failure_handling.py` (4 passing).
>
> **One bug was found in review and fixed:** the `ai_attempts < batch_max_attempts` filter was applied to the explicit `message_ids` path as well as auto-select, so bisect children stopped loading once attempts hit the ceiling. Any batch larger than `2 ** (batch_max_attempts - batch_bisect_after)` — **4** with the defaults, against a production batch size of **15** — stalled at `attempts == max` with `processing_status = PENDING`: never processed, never quarantined, invisible. The original tests passed only because the fixture had exactly 4 messages, sitting precisely on the boundary. Regression guard: `test_bisect_chain_quarantines_whole_production_batch`.
>
> Keep the rest of this section for context; do not re-implement it.

#### Problem
Step 1 fixed silent data loss but introduced a stall. `process_message_batch` now returns `"extraction_failed"` and leaves `ai_processed = False` when extraction fails. There is no attempt counter, no bisect, and no quarantine. A message that reliably makes the model emit unparseable JSON blocks its entire group **forever** — same 15 messages retried every 2 minutes, no progress, no alarm.

#### Changes

**1. Add an attempt counter.**

`backend/app/models.py`, `RawMessage`:
```python
ai_attempts = Column(Integer, default=0, nullable=False, index=True)
```

Migration `0005_raw_message_ai_attempts.py` (down_revision `0004_pipeline_p0_correctness`), plus the mirror in `startup_migrations.py`.

**2. Make the batch targetable.**

Bisect requires processing an explicit subset. Change the signature:
```python
@celery_app.task(name="app.tasks.process_message_batch", base=RateLimitedTask)
def process_message_batch(group_id: str, message_ids: list[str] | None = None):
```
- `message_ids is None` → select the 15 oldest eligible (current behaviour)
- otherwise → load exactly those rows, scoped to `group_id`

**3. Use the dispatch cycle as the retry mechanism.**

Do **not** hold a worker with `time.sleep` or Celery `retry_backoff`. The dispatcher already re-runs; `ai_attempts` is the counter. This is simpler than the "retry 3× with exponential backoff" in the original spec and equally effective.

On `events is None`:
```python
# increment attempts for every message in this batch
db.query(RawMessage).filter(RawMessage.id.in_(all_ids)).update(
    {"ai_attempts": RawMessage.ai_attempts + 1}, synchronize_session=False
)
db.commit()

attempts = max(m.ai_attempts for m in unprocessed) + 1

if attempts >= settings.batch_bisect_after and len(unprocessed) > 1:
    mid = len(unprocessed) // 2
    left  = [str(m.id) for m in unprocessed[:mid]]
    right = [str(m.id) for m in unprocessed[mid:]]
    process_message_batch.delay(group_id, left)
    process_message_batch.delay(group_id, right)
    return f"bisected_{len(left)}_{len(right)}"

if len(unprocessed) == 1 and attempts >= settings.batch_max_attempts:
    unprocessed[0].processing_status = ProcessingStatus.QUARANTINED
    db.commit()
    logger.error("Quarantined poison message %s after %d attempts",
                 unprocessed[0].id, attempts)
    return "quarantined"

return "extraction_failed"
```

**4. CRITICAL — exclude exhausted and quarantined rows from selection.**

Without this, quarantine does not stop the loop and the whole change is pointless. Add to **both** the dispatcher query and the batch selector:
```python
RawMessage.ai_attempts < settings.batch_max_attempts,
RawMessage.processing_status != ProcessingStatus.QUARANTINED,
```

**5. Reset attempts on success.** In the success and all-noise branches, include `"ai_attempts": 0` in the update dict so a group that recovers isn't permanently penalised.

**6. Config** (`backend/app/config.py`, follow the existing `_get_int`/`_get_float` pattern and add to the `__init__` re-read block):
```python
batch_max_attempts: int   = _get_int("BATCH_MAX_ATTEMPTS", 5)
batch_bisect_after: int   = _get_int("BATCH_BISECT_AFTER", 3)
```

#### Optional refinement
`AgnesService.classify_and_extract_batch` returns `None` for both HTTP failure and unparseable JSON. Bisecting only helps for parse failures — a network outage should retry whole. If you want the distinction, return a small result object or raise a typed exception for transient errors, and only bisect on parse failures. Not required for correctness.

#### Acceptance criteria
- [ ] A message that always fails to parse ends `QUARANTINED` and stops being selected
- [ ] The rest of its group continues processing after the bisect isolates it
- [ ] A transient failure recovers with `ai_attempts` back to 0, no data lost
- [ ] `ai_processed` is never `True` on a failure path
- [ ] Unit test: mock `extract_batch_via_agnes` → `None`, assert bisect fan-out and eventual quarantine
- [ ] Unit test: mock success after 2 failures, assert `ai_attempts == 0` and events created

---

### 3C. Index reconciliation

#### Problem
`_parse_batch_json` carries `"index": item.index` (`agnes_service.py` ~323), but `extract_batch_via_agnes` drops it when building `results`, and the writer attributes every event to `unprocessed[0]`:
```python
# TODO(step-3): honour item.index ...
first_raw = unprocessed[0]
```
For a batch of 15 producing 4 events, three have a wrong `source_message_id`.

#### Changes

**1. Thread the index through `extract_batch_via_agnes`.** For each item, capture `item.get("index")` and stamp it on every wrapped event from that item:
```python
src_index = item.get("index")
...
wrapped["_source_index"] = src_index   # 1-based, per the prompt
results.append(wrapped)
```
Use a leading underscore to mark it as internal plumbing — it must not reach the DB row.

**2. Validate in the writer.** Build the map and validate hard:
```python
index_to_raw = {i + 1: m for i, m in enumerate(unprocessed)}

if len(events) and any(e.get("_source_index") is None for e in events):
    logger.warning("Agnes omitted index on %d/%d event(s) for group %s",
                   sum(1 for e in events if e.get("_source_index") is None),
                   len(events), group.id)

seen = [e.get("_source_index") for e in events if e.get("_source_index")]
if len(seen) != len(set(seen)):
    logger.warning("Agnes returned duplicate indices for group %s: %s", group.id, seen)
```
Per event:
```python
idx = event_data.pop("_source_index", None)
src_raw = index_to_raw.get(idx) if isinstance(idx, int) else None
if src_raw is None:
    logger.warning("Unmappable index %r for group %s; attributing to batch head", idx, group.id)
    src_raw = unprocessed[0]
```
Then `source_message_id = src_raw.message_id`. After step 5, also set `source_raw_message_id = src_raw.id`.

**3. Anchor the timestamp per message.** `process_message_batch` currently uses `anchor = unprocessed[0].created_at` for the whole batch. Once indices are mapped, relative dates should resolve against **that event's own source message**. Batches span up to 15 messages; if they cross midnight, "tomorrow" resolves to the wrong day. Pass the per-message anchor into normalisation.

> This matters more after step 4, when `date_expression` is resolved locally. Wire the per-message anchor now so step 4 has it.

**4. Strengthen the prompt.** `BATCH_PROMPT` rule 1 already says "Return ONE item per message matching its index." Add: "The `index` field is REQUIRED on every item and MUST equal the message number as given. Never renumber, never omit, never merge two messages into one item."

#### Acceptance criteria
- [ ] Batch of 5 where messages 2 and 4 yield events → those events carry message 2's and 4's `message_id`
- [ ] Missing / out-of-range / duplicate index → falls back to batch head, logs a warning, does not crash
- [ ] `_source_index` never appears on an `AcademicEvent` or in an API response
- [ ] Per-event anchor threaded through to date resolution

---

### 3A. Real batch triggers

#### Problem
`dispatch_message_batches` fires any group with ≥1 unprocessed message on a fixed 2-minute beat. A lone message always waits up to 2 minutes; a 60-message burst spreads over four cycles.

#### Changes

**1. Beat becomes a cheap poller.** `celery_app.py`: change `dispatch-message-batches` from `crontab(minute="*/2")` to `30.0` (seconds). An "age > 90 s" trigger cannot fire on a 2-minute beat — the decision must move into the dispatcher and the poll must be finer-grained than the threshold.

**2. Aggregate per group in one query:**
```python
rows = (
    db.query(
        RawMessage.group_id,
        func.count(RawMessage.id).label("pending"),
        func.min(RawMessage.created_at).label("oldest"),
    )
    .join(WhatsAppGroup, WhatsAppGroup.id == RawMessage.group_id)
    .filter(
        RawMessage.ai_processed == False,
        RawMessage.message_text.isnot(None),
        RawMessage.message_text != "",
        RawMessage.ai_attempts < settings.batch_max_attempts,
        RawMessage.processing_status != ProcessingStatus.QUARANTINED,
        WhatsAppGroup.is_active == True,
        WhatsAppGroup.coverage_state == CoverageState.ACTIVE,
    )
    .group_by(RawMessage.group_id)
    .all()
)
```

**3. Decide per group:**
```python
if pending >= settings.batch_size_trigger:                    reason = "size"
elif (now - oldest).total_seconds() > settings.batch_age_trigger_seconds:
                                                              reason = "age"
elif _group_has_tripwire(db, gid):                            reason = "tripwire"
else:                                                          continue
```

**4. Tripwire — use portable SQL.** The test suite runs on SQLite, which has no `ILIKE`. Use:
```python
from sqlalchemy import or_, func as sqlfunc
lowered = sqlfunc.lower(RawMessage.message_text)
or_(*[lowered.like(f"%{term}%") for term in settings.batch_tripwire_terms])
```
Terms: `cancel`, `postpon`, `no class`, `venue`, `reschedul`, `today`, `now`, `urgent`.

The tripwire decides **priority, not classification**. A false positive only costs an earlier LLM call. Do not let it influence whether an event is created.

**5. CRITICAL — add a per-group dispatch lock.**

At a 30-second beat, a still-running batch job will be dispatched again, putting two workers on the same group and double-processing the same rows. This was not in the original spec and it is the most likely way to break step 3A.

Reuse the pattern in `scheduler.py` (`_acquire_scheduler_lock`, ~26). Redis is already a dependency:
```python
# in the dispatcher, before .delay()
if not redis.set(f"knowtis:batch_lock:{gid}", "1", nx=True, ex=300):
    continue        # a batch for this group is already in flight
```
Release in `process_message_batch`'s `finally` block. The 300 s TTL is the crash-safety net.

> **The lock must not block bisect children.** 3B's failure path enqueues two `process_message_batch(group_id, subset)` jobs for the *same group*. A naive per-group lock blocks the second child, and its messages stall until the TTL expires. Either key the lock on the group only for the **auto-select** path (`message_ids is None`) and let explicit-subset calls through, or key it on a hash of the id set. Explicit subsets are disjoint by construction, so they cannot double-process.

**6. Config:**
```python
batch_size_trigger: int          = _get_int("BATCH_SIZE_TRIGGER", 15)
batch_age_trigger_seconds: float = _get_float("BATCH_AGE_TRIGGER_SECONDS", 90.0)
batch_tripwire_terms: tuple      = (...)  # as above
```

**7. Log the reason** on every dispatch. Without it you cannot tell whether the triggers are behaving.

**8. Remove the two `TODO(step-3)` trigger markers.**

#### Acceptance criteria
- [ ] 1 message, quiet group → dispatched within ~90 s, not 2 min
- [ ] 20 messages arrive at once → dispatched immediately on the size trigger
- [ ] Message containing "class cancelled" → dispatched on the next 30 s tick
- [ ] Two ticks during a long-running batch → only one job runs (lock held)
- [ ] Lock released on both success and exception
- [ ] Tripwire query runs on SQLite (tests pass)

---

## 4. STEP 4 — Temporal rewrite, prompt change, and the big deletion

Largest step, highest visible payoff. Three parts; land them together because they are interdependent.

### 4A. Stop the LLM doing date arithmetic

#### Prompt changes (`agnes_service.py`)
In both `EXTRACTION_SYSTEM_PROMPT` and `BATCH_PROMPT`, replace the `date_time` field:
```
"date_expression": "the temporal phrase exactly as written in the message, e.g. 'next friday 2pm', 'tomorrow', '30th', or null",
"date_is_explicit": true if the message states a date or day, false if it is vague ("soon", "next week sometime")
```
Delete the rule that says *"Use the explicit Day of Week and date from the reference timestamp anchor to resolve relative dates … into ISO-8601 UTC. Default missing time to 09:00:00 UTC."*

Add: *"Do NOT compute or resolve dates. Copy the temporal phrase as written. Date resolution happens downstream."*

Also **remove `urgency_score`** from the requested fields — step 6 derives it locally. Keep `confidence_score`, `relevance_score`, `actionability_score`, `needs_review`, `event_completeness`.

#### Schema (`backend/app/schemas.py`, `ExtractedEventItem`)
Replace `date_time: Optional[str]` with:
```python
date_expression: Optional[str] = Field(default=None, ...)
date_is_explicit: bool = Field(default=False)
```
Keep `date_time` as an accepted-but-ignored field for one release so an older model response does not hard-fail validation. Log when it appears.

#### Wiring (`_wrap_batch_result`)
Replace the `datetime.fromisoformat` block with:
```python
date_time, date_precision = TemporalParser.resolve(
    agnes.get("date_expression"),
    anchor=msg_created_at,          # per-message anchor from 3C
    explicit=bool(agnes.get("date_is_explicit")),
)
```
Return `date_precision` in the event dict.

### 4B. Rewrite `TemporalParser`

New public API:
```python
class DatePrecision(str, Enum):
    EXACT     = "EXACT"       # date + time known
    DAY_ONLY  = "DAY_ONLY"    # date known, time unknown — do NOT fabricate 09:00
    UNKNOWN   = "UNKNOWN"     # nothing resolvable

@staticmethod
def resolve(expression: Optional[str],
            anchor: Optional[datetime] = None,
            explicit: bool = False) -> tuple[Optional[datetime], DatePrecision]
```

Bugs that **must** be fixed (all verified in the current file):

1. **Text order, not dict order.** Current code iterates `WEEKDAYS` (`monday` first) and `break`s on first match, so *"Test moved from Monday to Friday"* → Monday. Build one combined regex, `finditer` it, and select by **match position in the string**.
2. **`this` / `next` / `coming` are captured then discarded**, so `next Friday` == `this Friday`. Honour them: `next X` = X in the following week; bare `X` / `this X` = the coming X.
3. **`days_ahead <= 0 → += 7`** pushes "this Monday" said on a Monday a week out. Should be `< 0`; on an equal weekday, keep today if the resolved time is still ahead of the anchor.
4. **Numeric dates assume DD/MM with no disambiguation.** `12/25/2024` raises `ValueError` and silently yields `None`. Disambiguate: first component > 12 → DD/MM; second > 12 → MM/DD; otherwise DD/MM (Nigerian convention). Never let a `ValueError` become a silent `None` — log it.
5. **Missing time silently becomes 09:00.** Return `DAY_ONLY` instead and let the reminder layer decide. Fabricating 9am creates false "due at 9am" reminders.

New coverage required:
- Ordinals: `30th`, `1st of June`, `June 30th`, `on the 15th`
- Relative spans: `in 2 days`, `in a week`, `next week`, `end of the week` → Friday, `end of the month`
- Times: `noon`, `midnight`, `11:59pm`, `half past 2`, `2.30pm`, ranges `2-4pm` → take the start
- Combined: `friday 2pm`, `2pm on friday`, `by 5pm tomorrow`
- Reject: bare `?`, empty, `soon`, `later` → `(None, UNKNOWN)`

Timezone handling stays as-is: resolve in `app_tz()`, store naive UTC via `to_naive_utc`. Keep `has_date_reference` if anything still calls it; otherwise delete.

#### Fixture corpus — required
Create `backend/tests/fixtures/temporal_cases.py`:
```python
# (expression, anchor_iso, expected_dt_iso_or_None, expected_precision)
CASES = [
    ("tomorrow",            "2026-08-21T10:14:00", "2026-08-22", "DAY_ONLY"),
    ("friday 2pm",          "2026-08-21T10:14:00", "2026-08-21T14:00", "EXACT"),
    ("next friday",         "2026-08-21T10:14:00", "2026-08-28", "DAY_ONLY"),
    ("from monday to friday","2026-08-21T10:14:00","2026-08-28", "DAY_ONLY"),  # last wins? decide + document
    ...
]
```
**Minimum 60 cases**, drawn from real group messages where possible. Document the tie-break rule for multi-date expressions and assert it — the current implicit behaviour is a bug, so the new behaviour must be an explicit decision.

### 4C. Delete the dead classifier stack

`_extract_legacy` already carries a `DEPRECATED … Removed in step 4` marker. Nothing in production calls the legacy path; the only caller of `extract_events` is `backend/tests/unit/test_classifier.py`.

**Delete:**
- `backend/app/services/semantic_classifier.py` — whole file (~332 L). Also remove its `prewarm()` call if `main.py` invokes it at startup.
- `backend/app/services/setfit_classifier_service.py` — move under `backend/training/` or delete. It silently never loads in production (`setfit_classifier_path` absent), so every message currently falls through to regex.
- `event_extraction_service.py`: `extract_event`, `extract_events`, `_extract_legacy`, `_is_peer_question_or_non_event`, `_is_bare_fragment`, `_assess_actionability`, `_event_completeness`, `_extract_via_llm`
- `classifier_service.py`: `classify_message`, `classify_local_category`, `classify_single_shot`, `classify_event_type`, `calculate_scores`, all `_RE_*` matchers, and the keyword machinery added while fixing the substring bug (`_exact_keyword_regex`, `_stem_keyword_regex`, `_count_keywords`, `_SIGNAL_KEYWORDS`, `_NOISE_KEYWORDS`, `_NOISE_EMOJI`)

**Keep** in `classifier_service.py`: `Classification`, `EventCategory`, `ClassifierCategory`, `CATEGORY_MAP`, `LOCAL_CATEGORY_TO_CLASSIFIER`, `category_to_classifier`. File should end up ~60 lines.

> Two latent substring bugs die with this deletion and need no separate fix: `"test"` matching `"latest"` and `"exam"` matching `"example"` in `calculate_scores`, and the same pattern in `_is_bare_fragment`.

### 4D. Add the prefilter

New file `backend/app/services/prefilter.py`:
```python
def classify_skip(text: str, group_id, db) -> Optional[ProcessingStatus]:
    """Return a SKIPPED_* status when the message should never reach the LLM."""
```
Rules — **deterministic and free only**:
1. empty / whitespace / media-only marker → `SKIPPED_EMPTY`
2. fewer than 4 tokens **and** no action verb → `SKIPPED_FRAGMENT`
3. `text_hash` already seen in this group within 24 h → `SKIPPED_REPEAT`

Everything else passes. **No `endswith("?")` rule. No keyword scoring. No SetFit. No embeddings.**

Requires `RawMessage.text_hash = Column(String(64), index=True)` — sha256 of normalised text, computed in `ingest_message`. Include it in step 4's migration (`0006_prefilter_text_hash.py`).

Call the prefilter at the top of `process_message_batch`: mark skips with their status **and** `ai_processed = True` (they are terminally decided), and send only survivors to Agnes.

> Rule 2 is safe now that batching exists. Consecutive fragments — `"Class cancelled"` / `"for tomorrow"` / `"ELE310"` — are merged by the batch prompt seeing them together, which is precisely what the deleted `_is_bare_fragment` + 15-minute sliding window were trying to patch.

### 4E. Rewrite the test file

`backend/tests/unit/test_classifier.py` (~284 L) tests functions being deleted. It must be rewritten, not deleted — port the intent:
- signal/noise expectations → prefilter tests + Agnes-mocked pipeline tests
- fragment expectations → prefilter `SKIPPED_FRAGMENT` tests
- temporal expectations → the new fixture corpus

Budget real time for this. It is the largest hidden cost in step 4.

#### Acceptance criteria
- [ ] All 60+ temporal fixtures pass
- [ ] `"Test moved from Monday to Friday"` resolves per the documented rule, not dict order
- [ ] `next Friday` ≠ `this Friday`
- [ ] No code path fabricates 09:00; missing time → `DAY_ONLY`
- [ ] `12/25/2024` does not silently yield `None`
- [ ] Agnes prompt no longer requests `date_time` or `urgency_score`
- [ ] `semantic_classifier.py` and the legacy extractor are gone; imports clean
- [ ] Prefilter marks empty/fragment/repeat without an LLM call
- [ ] Test suite ≥ 30 passing

---

## 5. STEP 5 — Schema migration

Migration `0007_pipeline_schema.py`. Mirror everything in `startup_migrations.py`.

### 5A. `academic_events` columns
```
+ status                 ACTIVE | CANCELLED | SUPERSEDED   default ACTIVE, indexed
+ superseded_by_id       uuid fk academic_events.id  ON DELETE SET NULL
+ date_precision         EXACT | DAY_ONLY | UNKNOWN  default UNKNOWN
+ source_raw_message_id  uuid fk raw_messages.id     ON DELETE SET NULL, indexed
+ event_index            int default 0
+ revisions              jsonb (PG) / JSON (SQLite)  default '[]'
```
Keep the existing `source_message_id` String column for one release; backfill `source_raw_message_id` from it where a match exists, then stop writing the old one.

### 5B. Constraints and indexes
```sql
-- structural duplicate prevention
ALTER TABLE academic_events
  ADD CONSTRAINT uq_event_source
  UNIQUE (user_id, source_raw_message_id, event_index);

-- business dedup key
CREATE INDEX ix_events_business_key
  ON academic_events (user_id, course_code, event_type, date_time);
```
Note: in PostgreSQL, `NULL`s do not collide in a unique constraint, so existing rows and manual/OCR-created events (which have no source message) are unaffected. That is intended.

**This constraint is only meaningful if 3C is done.** If every event in a batch still claims `unprocessed[0]`, the constraint will reject legitimate distinct events from the same message. Verify 3C first, and set `event_index` to the event's ordinal within its source message.

### 5C. pgvector — do not change the column type in place
`embedding` is currently `Column(String)` holding a JSON array. An in-place type change risks the whole table. Use a parallel column:

1. `CREATE EXTENSION IF NOT EXISTS vector;`
2. Add `embedding_vec Vector(384)` (nullable)
3. Backfill in a bounded background job: parse the JSON string → vector, batch a few thousand rows at a time
4. Switch `find_duplicate` and `search_service` reads to `embedding_vec` with a fallback while backfill is incomplete
5. `CREATE INDEX ... USING hnsw (embedding_vec vector_cosine_ops)` after backfill
6. Drop `embedding` in a **later** migration, once you have observed a clean release

**SQLite guard.** Tests run on SQLite, which has no pgvector. Gate on `bind.dialect.name == "postgresql"` in the migration, and keep a Python-cosine fallback in `find_duplicate` selected by dialect. `backend/app/services/search_service.py` already issues raw SQL that assumes PostgreSQL — verify it is either PG-only or dialect-guarded before you add more.

### 5D. Rewrite `find_duplicate`
Business key first, vectors second:
```python
# 1. exact business key — indexed, free, catches most real duplicates
if course_code and event_type and date_time:
    hit = query(user_id, course_code, event_type, date(date_time)).first()
    if hit: return hit

# 2. vector fallback only when the business key is incomplete
#    ORDER BY embedding_vec <=> :q LIMIT 1, threshold 0.92
```
Raise the threshold from 0.88 to **0.92**. At 0.88 with `canonical_dedup_text`, `"CSC301 Assignment 1"` and `"CSC301 Assignment 2"` are at real risk of merging. Delete the Python `for event in recent_events` cosine loop.

### 5E. Replace the `[CANCELLED]` title prefix
`reconcile_event` currently does `target.title = f"[CANCELLED] {target.title}"`. A title prefix is not queryable and poisons the next dedup pass. Replace with `status = CANCELLED`, and:
- cancel pending reminders for that event
- append a `revisions` entry recording what changed and which message caused it
- on `UPDATE`, append to `revisions` rather than concatenating into `description`

Also fix the targeting bug: `matching_events[0]` (newest by `created_at` for that course) has no `event_type` filter, no date proximity, no title similarity. Target by `(course_code, event_type, nearest date_time within ±7 days)`.

### 5F. Propagate
- `AcademicEventResponse` (`schemas.py`): add `status`, `date_precision`, `needs_review`, `group_id`, `source_group_jid`
- `events_routes`: filter `status != SUPERSEDED`; keep `is_archived == False`, `is_duplicate == False`
- `frontend/src/lib/events.ts` `AcademicEvent`: add the same fields (see §7)

#### Acceptance criteria
- [ ] Migration is reversible and runs clean on both PG and SQLite
- [ ] Reprocessing the same message twice creates no second row
- [ ] Business-key dedup hits without touching a vector
- [ ] `"Assignment 1"` and `"Assignment 2"` for the same course do **not** merge
- [ ] Cancellation sets `status = CANCELLED`, kills pending reminders, leaves the title clean
- [ ] `startup_migrations.py` mirrors every change

---

## 6. STEP 6 — Derived urgency

### Problem
`urgency_score` comes from keyword presence (`calculate_scores`: 0.5 / 0.8 / 0.9 on `urgent` / `tomorrow`) or from whatever Agnes guessed, and it is the **primary sort key** of the dashboard and the night brief (`notifications_routes.py` ~175 orders by `urgency_score.desc()`). An assignment due in 4 hours ranks below a seminar next month that said "urgent".

**Depends on step 4.** Deriving urgency from `date_time` while `date_time` is often wrong just makes the wrong item sort confidently to the top.

### Implementation
New `backend/app/services/urgency_service.py`:
```python
BASE = {"DEADLINE": 1.0, "ALERT": 0.9, "EVENT": 0.7, "INFO": 0.4}
HORIZON_HOURS = 168.0   # 1 week

def compute_urgency(event, now=None) -> float:
    now = now or datetime.utcnow()
    if event.status == "CANCELLED":
        return 0.0
    base = BASE.get(str(event.event_type), 0.5)
    if event.date_time is None:
        return round(base * 0.5, 3)          # unscheduled: type only
    hours = (event.date_time - now).total_seconds() / 3600.0
    if hours < 0:
        return 0.05                          # past
    decay = max(0.0, min(1.0, 1.0 - hours / HORIZON_HOURS))
    u = base * 0.4 + decay * 0.6
    if str(event.event_type) == "ALERT":
        u = max(u, 0.75)                     # alerts stay visible
    conf = event.confidence_score or 0.8
    return round(max(0.0, min(1.0, u * (0.7 + 0.3 * conf))), 3)
```

**Keep the stored column** — you need it indexed to sort cheaply. Recompute it:
- on write, in `process_message_batch` and `reconcile_event`
- periodically, folded into the existing 5-minute reminder job (`scheduler.py` ~81, `_execute_pending_reminders`), scoped to `date_time > now() - 24h` so the work stays bounded
- add `CREATE INDEX ix_events_urgency ON academic_events (user_id, urgency_score DESC)`

Stop consuming Agnes's `urgency_score` (already removed from the prompt in step 4). Keep `confidence_score` and `relevance_score` from the model.

`DAY_ONLY` precision: treat the time as end-of-day for urgency so an item due "Friday" does not read as due 00:00 Friday.

#### Acceptance criteria
- [ ] Assignment due in 4 h outranks a seminar 30 days out that says "urgent"
- [ ] Cancelled events sort to the bottom
- [ ] Unscheduled events rank below scheduled ones of the same type
- [ ] Alerts never sink below 0.75 while active
- [ ] Recompute job is bounded and idempotent
- [ ] Unit tests over a table of `(type, hours_until, confidence) → expected band`

---

## 7. STEP 7 — Provenance, correction loop, UI

Frontend is a static Capacitor export. Re-locate components by name before editing; the tree has uncommitted changes.

Reference paths (verified this session): `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/dashboard/dashboard-components.tsx` (`StickyNote`, `CoverageBanner`), `frontend/src/components/dashboard/event-detail-modal.tsx`, `frontend/src/app/updates/page.tsx`, `frontend/src/lib/events.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/store.ts`, `frontend/src/components/layout/bottom-nav.tsx`.

### 7A. Provenance

**Backend.** `group_id` and `source_group_jid` are already persisted and serialized, but no human-readable group name is. Add `group_name` to `AcademicEventResponse` via a join or a lightweight subquery in `events_routes` — do not N+1 per event.

**Frontend types.** `frontend/src/lib/events.ts` currently declares only `id, event_type, course_code?, title, description?, venue?, date_time?, urgency_score, confidence_score, relevance_score?, actionability_score?, is_duplicate, created_at`. Add: `group_id?`, `group_name?`, `source_group_jid?`, `needs_review`, `status`, `date_precision`.

**Render it.** Currently nothing shows a source, while the dashboard section is literally titled *"Latest from Groups"*:
- `StickyNote` — add the group name as a subtle caption
- "Latest from Groups" rows — show `group_name` next to the relative time
- `EventDetailModal` — it says `"Extracted {created_at}"`; change to `"From {group_name} · {created_at}"`
- `/updates` cards — same treatment

**Respect `date_precision`.** A `DAY_ONLY` event must render as "Friday", never "Friday 9:00 AM". Fabricated precision in the UI is worse than admitting the time is unknown.

### 7B. Correction loop

This is the highest-leverage product change in the whole plan: it fixes perceived precision **and** generates the labelled data that could later replace most Agnes calls.

**Backend gaps:**
1. `POST /api/v1/training/feedback` exists (`training_routes.py` ~41) but keys on `prediction_id`. The client has an `event_id`. Either accept `academic_event_id` in the payload and look up the `PredictionRecord` (it stores `academic_event_id`), or add `GET /training/predictions?academic_event_id=`.
2. **There is no `PUT`/`PATCH /events/{id}` anywhere.** The "corrected" feedback type is unusable without it. Add one, restricted to `title`, `course_code`, `date_time`, `venue`, `event_type`, and have it set `needs_review = False` and append to `revisions`.
3. On `confirmed_correct`, clear `needs_review` on the **`AcademicEvent`**, not only on the `PredictionRecord`.

**Frontend:**
1. Add `trainingApi` to `frontend/src/lib/api.ts` — it does not exist. Methods: `submitFeedback(eventId, type, corrections?)`, `updateEvent(id, patch)`.
2. Confirm chip on any card with `needs_review === true`: "Looks right?" → ✓ / ✕ / Edit. **48×48 px minimum touch targets.**
3. Optimistic update in the Zustand store, rollback on failure.
4. `✕` → `reported_noise` → archive locally.

Note `deleteEvent` is currently only reachable from `/events`, which is **not** in `bottom-nav.tsx`. Either add archive to the dashboard/updates cards or route users to it.

### 7C. Tier truncation signal
`events_routes` caps free users at 3 items while the dashboard requests 24, with no UI signal. Return `total` and either `truncated: bool` or `plan_limit: int`, and render "Showing 3 of 12 — upgrade to see all". Silent truncation currently reads as "the app missed my deadlines".

### 7D. Optional — connect realtime
`WS /ws/feed` and `GET /feed/stream` (SSE) exist in `backend/app/routes/realtime_routes.py` with **no client consumer**; freshness depends entirely on pull-to-refresh. Native push via `@capacitor/push-notifications` is the de-facto live channel and may be sufficient. If you wire the WS, do it in a store-level singleton with reconnect/backoff, and keep push as the background path.

#### Acceptance criteria
- [ ] Every auto-extracted card names its source group
- [ ] `DAY_ONLY` events never display a fabricated time
- [ ] Confirm/reject reachable from `/dashboard` and `/updates`, not only `/events`
- [ ] `PUT /events/{id}` exists and is exercised by the Edit path
- [ ] Confirming clears `needs_review` on the event and persists a `TrainingFeedback` row
- [ ] Truncated lists say so
- [ ] Touch targets ≥ 48×48 px; safe-area insets intact; `BottomNav` unchanged
- [ ] No Web Notification / Web Push API introduced anywhere

---

## 8. Accepted risks and non-goals

- **Steps 1–3 change nothing a user notices.** They stop data loss, duplication, and mis-cancellation. Visible quality arrives in 4, 6, 7. Do not report steps 1–3 as quality improvements.
- **`_extract_legacy` stays until step 4.** It is dead in production but retained as a documented fallback. Do not "fix" it — it is scheduled for deletion.
- **Substring bugs in `calculate_scores` and `_is_bare_fragment`** (`"test"` in `"latest"`, `"exam"` in `"example"`) are knowingly unpatched; both functions are deleted in step 4.
- **`source_message_id` remains a `String(255)`** alongside the new FK for one release, to keep the migration reversible.
- **SetFit is not reintroduced** until the step 7 feedback loop has produced real labels. Reintroducing it earlier just adds a silently-never-loading tier, which is what the current code does.

---

## 9. Per-step done checklist

A step is done only when all four hold:

1. Acceptance criteria in its section are met
2. `python -m pytest tests -q` from `backend/` shows **≥ 30 passed, 0 failed**
3. `python -c "import app.tasks, app.scheduler, app.celery_app, app.main"` succeeds
4. Any schema change is in **both** `backend/alembic/versions/` and `backend/app/startup_migrations.py`

Additionally, remove the corresponding `TODO(step-N)` markers from the code when the step lands. If a `TODO` must survive, renumber it to the step that will actually address it.
