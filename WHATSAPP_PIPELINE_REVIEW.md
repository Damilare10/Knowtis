# WhatsApp Pipeline Review — Handoff

Audit of the WhatsApp message pipeline: ingestion → classification → filtering → extraction → persistence → dashboard.

**Every finding below was verified by reading the cited file and line.** Do not re-explore the codebase to confirm them — go straight to implementation. No code was changed during the audit; this is a review only.

---

## 1. Pipeline as currently built

```
WhatsApp connector (HTTP poll, every 2 min — celery_app.py:57)
  └─ whatsapp_listener_service.ingest_message:126
       ├─ MessageClassifier.classify_message      (SetFit → semantic → regex)
       └─ if SIGNAL → EventExtractionService.extract_event:95
                        └─ _extract_legacy:109      ← regex/NER/rules ONLY, no Agnes
                             ├─ classify_local_category  (classifies a SECOND time)
                             ├─ NERService.extract_entities
                             ├─ TemporalParser.parse_date_time
                             └─ LLM fallback only when "uncertain"
                        → DeduplicationService.reconcile_event → AcademicEvent
```

Two more **independent writers** hit the same table:

| Writer | Schedule | Path | Dedup? |
|---|---|---|---|
`drive_listener` | 2 min — celery_app.py:57 | legacy regex only | yes (`reconcile_event`) |
`process_agnes_batch_task` | 30 min — celery_app.py:73 | Agnes batch | **none** |
`scheduler._run_ai_chat_batch_parse` | 30 min — scheduler.py:566 | Agnes batch, 2 h window | yes |

---

## 2. P0 — broken, causing silent data loss

### 2.1 `AcademicEvent.needs_review` does not exist
`AcademicEvent` columns are models.py:147-168 — no `needs_review`. The column lives on `PredictionRecord` (models.py:451).

- tasks.py:271 — `AcademicEvent.needs_review == True` in a query filter → `AttributeError` at query build
- tasks.py:304 — assigns it to an `AcademicEvent` instance → transient Python attribute, never persisted
- tasks.py:327 — reads that transient value to gate notifications

**Effect:** the entire reply / sliding-window context-recovery branch (tasks.py:257-342) is dead.

### 2.2 `ProcessingStatus` is missing members that the code writes
Enum is `PENDING | PROCESSED | FAILED` (models.py:49-53). Column is `SQLEnum(ProcessingStatus)` (models.py:192).

- tasks.py:363 writes `"QUARANTINED"`
- tasks.py:405 writes `"FILTERED_OUT"`

**Effect:** the submission gate and `filter_mode == "FILTERED"` both raise on commit.

### 2.3 `from app.models import Event` — no such model
event_extraction_service.py:43. `models.py` defines only `AcademicEvent`. `ImportError` is swallowed by `except Exception` + `logger.debug` at :56-57.

**Effect:** canonical course-code alignment in `align_course_code` has never run in production, and never logged that fact.

### 2.4 `action_type` is silently dropped → UPDATE/CANCEL never fire
- Agnes prompt requests it — agnes_service.py:25
- Schema declares it — schemas.py:609 (`ExtractedEventItem.action_type`)
- `reconcile_event` reads it — deduplication_service.py:102, defaults to `"CREATE"`
- **`_wrap_batch_result` return dict omits it** — event_extraction_service.py:336-353

**Effect:** "CSC301 test cancelled" creates a *second* card instead of cancelling the first. Reminders keep firing for cancelled classes. Highest-impact user-facing bug.

### 2.5 Batch failure marks up to 50 messages permanently processed
tasks.py:576-584:

```python
events = EventExtractionService.extract_batch_via_agnes(messages_payload)
if not events:
    db.query(RawMessage).filter(RawMessage.id.in_(all_ids)).update(
        {"ai_processed": True}, synchronize_session=False)
```

`not events` conflates three unrelated outcomes:
- legitimately all-noise → marking processed is correct
- invalid JSON from the model — agnes_service.py:296 returns `None`
- network error / timeout / rate limit — event_extraction_service.py:255 returns `None`

**Effect:** one Agnes timeout silently destroys a group's academic backlog. Only a `logger.warning` behind it. Most dangerous line in the pipeline.

### 2.6 Three writers, one table, different rules
See table in §1. Additionally scheduler.py:388-397 queries a **2-hour window with no `ai_processed` filter** and runs every 30 min → each message reprocessed ~4×. Combined with §2.7, a single message can hit Agnes ~5 times.

### 2.7 `process_agnes_batch_task` has zero deduplication
tasks.py:586-609 — bare `db.add()`, `source_message_id=None` (tasks.py:606). Guaranteed duplicates against rows the listener already created ~28 minutes earlier.

### 2.8 Agnes never runs on the hot path
whatsapp_listener_service.py:198 calls `extract_event` (**singular**) → event_extraction_service.py:106 → `_extract_legacy`. Agnes only exists inside `extract_events` (**plural**, :62-92), which the listener never calls.

**Effect:** the 2-minute path is pure regex. The good LLM result arrives 30 min later as a separate row.

### 2.9 Embeddings computed from three different base strings into one column
- listener — whatsapp_listener_service.py:227 → `generate_embedding(text)` (raw message)
- tasks — tasks.py:377 → `title + description + course_code`
- scheduler — scheduler.py:460 → `title + description`
- dedup **queries** with — deduplication_service.py:105 → `title + description`

**Effect:** cosine similarity at threshold 0.88 compares incompatible vectors. Dedup is largely noise.

---

## 3. P1 — wrong output, not crashes

### 3.1 Weekday resolution uses dict order, not text order
temporal_parser.py:117-125 iterates `WEEKDAYS` (temporal_parser.py:29-37, `monday` first) and `break`s on first regex hit.

*"Test moved from Monday to Friday"* → resolves to **Monday**.

Also: `this|next|on|by|due` prefix is captured then discarded (:119), so `next Friday` == `this Friday`. And `days_ahead <= 0 → += 7` (:122-123) pushes "this Monday" said on a Monday a week out. `DATE_RE_NUMERIC` assumes DD/MM (:109) with no disambiguation. No ordinals, no "in 2 days", no "end of week", no ranges, no "noon"/"midnight". Missing time silently becomes 09:00 (:166-168).

### 3.2 `urgency_score` is keyword-derived but is the dashboard's primary sort key
classifier_service.py:319-323 — returns 0.5 / 0.8 / 0.9 based on the presence of `urgent` / `tomorrow`. Sorting uses `urgency_score DESC, date_time ASC` (also notifications_routes.py:175).

**Effect:** an assignment due in 4 hours ranks below a seminar next month that said "urgent". Single worst UX defect.

### 3.3 `confidence_score` is a hardcoded constant
classifier_service.py:325 → always `0.80`. It is passed as `model_confidence` (weight 0.15) into `ConfidenceScorer.calculate_confidence` at event_extraction_service.py:202. The real classifier confidence (`class_conf`, event_extraction_service.py:119) is only used for `field_confidences` (:207-212).

### 3.4 `endswith("?") → NOISE`
classifier_service.py:145,155 and duplicated at event_extraction_service.py:382. Course reps routinely write *"Class has moved to Hall B, ok?"* — dropped unless it matches a 3-regex override list (classifier_service.py:148-152).

### 3.5 Title is the first line of the message
event_extraction_service.py:143-148 → `"[CSC301] Good morning everyone"`.

### 3.6 Peer-inquiry regex block duplicated and already drifting
classifier_service.py:136-143 vs event_extraction_service.py:367-374 (verbatim copies). Their override lists differ: regexes at classifier_service.py:148-152 vs plain substrings at event_extraction_service.py:376-379.

### 3.7 Double gating can disagree, causing untraceable drops
whatsapp_listener_service.py:147 gates on `classify_message` → SIGNAL. Then event_extraction_service.py:119-124 re-gates on `classify_local_category` → `"noise"` → returns `None`. Row is stored `classification=SIGNAL, status=PROCESSED` with no event and no record of why.

### 3.8 Up to 4 SetFit inferences per message
`classify_message` (classifier_service.py:110-121) + `classify_local_category` (:83-89) + `classify_single_shot` (:289-296) + its nested `classify_message` (:300). Plus 3 MiniLM embeds elsewhere.

### 3.9 Deduplication is O(n) Python-side; pgvector is not wired
`embedding = Column(String)` (models.py:163) with the comment *"to be indexed with pgvector"*. deduplication_service.py:40-76 loads every non-duplicate row from the last 30 days, `json.loads` each embedding, loops in Python.

### 3.10 `reconcile_event` UPDATE/CANCEL targets the wrong row
deduplication_service.py:118 orders by `created_at DESC` and :121/:133 take `matching_events[0]` — newest for that course code. No `event_type` filter, no date proximity, no title similarity. Cancellation is applied as a `"[CANCELLED] "` title prefix (:135), which is not queryable and poisons the next dedup pass.

### 3.11 Batch response indices are never reconciled
agnes_service.py:299-334 iterates whatever the model returned and ignores `item.index` alignment against the input list. One dropped index shifts every subsequent event onto the wrong message.

---

## 4. Frontend gaps

- **Provenance blackout.** `group_id`, `source_group_jid`, `source_message_id` are persisted (models.py:149,164-165) and serialized (schemas.py:144,152-153) but absent from `frontend/src/lib/events.ts:13-27` and never rendered. The dashboard section is titled *"Latest from Groups"* and names no group.
- **No user correction path.** No `PUT`/`PATCH /events/{id}` exists. `POST /api/v1/training/feedback` (training_routes.py:41-72) supports `confirmed_correct` / `corrected` / `reported_noise` but there is no `trainingApi` in `frontend/src/lib/api.ts`. Archive-only, and archive is only reachable from `/events`, which is not in `bottom-nav.tsx:10-14`.
- **Silent tier truncation.** Dashboard requests `limit: 24`; backend returns 3 for free users (events_routes.py:26,65-70) with no UI signal.
- **Realtime built, never connected.** WS `/ws/feed` + SSE `/feed/stream` exist (realtime_routes.py:60-137) with no client `WebSocket`/`EventSource`. Freshness depends entirely on manual pull-to-refresh.
- Frontend is `output: "export"` (next.config.ts:4) — static Capacitor bundle, so no API routes or server actions. All data flows client → Zustand → axios → FastAPI.

---

## 5. Root cause

Not model quality. **Three pipelines, two classifier layers, and two extractors derive the same facts with different rules and no single owner of the write.** Every finding above is a symptom. A better model changes nothing until there is one path.

---

## 6. Target architecture

```
WhatsApp connector (poll 2 min)
  └─ ingest_message: persist RawMessage + text_hash. No classify, no extract.

process_message_batch(group_id)   ← THE ONLY WRITER to academic_events
  ├─ prefilter (deterministic, free)
  │    drop empty/media-only, <4 tokens with no action verb,
  │    text_hash repeat within 24h in same group.
  │    No "?" rule. No keyword scoring. No SetFit.
  ├─ Agnes batched call (~15 messages)
  │    returns action_type AND date_expression (NOT a resolved date_time)
  ├─ EventNormalizer
  │    align_course_code (cached) · TemporalParser.resolve · canonical_dedup_text
  ├─ reconcile
  │    CANCEL → status=CANCELLED + kill pending reminders
  │    UPDATE → patch in place + append to revisions
  │    business key (user, course, type, date::date) → skip/merge
  │    key incomplete → pgvector HNSW top-1, threshold 0.92
  │    else → INSERT (unique: user + raw_message + event_index)
  └─ urgency recompute job (every 5 min, folded into the existing reminder job)

GET /events → order by derived urgency, filter status != SUPERSEDED
Dashboard card → shows group name + confirm chip when needs_review
Confirm/correct/noise → TrainingFeedback → later trains SetFit as a tier that
                        short-circuits Agnes for high-confidence cases
```

### 6.1 Batch triggers

`limit(N)` is a **ceiling, not a threshold** — 3 unprocessed messages send a batch of 3. The real problem with the current design is cadence (30 min), not size. Three triggers per group, whichever fires first:

| Trigger | Condition |
|---|---|
Size | ≥ 15 unprocessed messages |
Age | oldest unprocessed > 90 s |
Bypass | tripwire keyword on ingest: `cancel`, `postponed`, `no class`, `venue`, `now`, `today` |

Worst-case latency 90 s instead of 30 min, while still batching bursts. The bypass tripwire decides **priority, not classification** — a false positive only costs an earlier LLM call. This is the one appropriate use for the keyword lists that currently make irreversible classification decisions.

### 6.2 Batch size ~15, not 40
Index misalignment risk (§3.11), attention dilution (2048 max_tokens at agnes_service.py:146 across 40 messages ≈ 50 output tokens each), and retry blast radius.

### 6.3 Batch failure handling
```
retry 3× with exponential backoff
  → still failing? split batch in half, recurse
  → single message still failing? processing_status = QUARANTINED, ai_processed stays FALSE
  → only ever set ai_processed = True on a successful parse
```
Distinguish all-noise from failure — currently conflated (§2.5).

### 6.4 Never let the LLM do date arithmetic
Return `date_expression: "next friday 2pm"` + `date_is_explicit: bool`; resolve deterministically in `TemporalParser` against `raw.created_at` + user timezone. Testable, auditable, and it removes the two-parallel-date-paths ambiguity. Resolver returns `(datetime | None, precision)` where precision ∈ `EXACT | DAY_ONLY | UNKNOWN`; `DAY_ONLY` suppresses time-of-day reminders instead of fabricating 09:00.

### 6.5 Urgency becomes derived
`urgency = f(hours_until_deadline, event_type, confidence)` with an ALERT floor, recomputed by the existing 5-minute job (scheduler.py:535). Store `date_time`; stop freezing a keyword guess.

### 6.6 One embedding contract
Single `canonical_dedup_text(event) = f"{event_type}|{course_code}|{title}"` used for both the stored vector and every query vector. Then real pgvector: `Vector(384)` + HNSW + `ORDER BY embedding <=> :q LIMIT 5`.

### 6.7 Batching replaces two workarounds
Consecutive fragments — `"Class cancelled"` / `"for tomorrow"` / `"ELE310"` — are unparseable individually. That is exactly what `_is_bare_fragment` (event_extraction_service.py:387-440) and the 15-minute sliding window (tasks.py:257-277, currently crashing per §2.1) try to patch. A batch prompt sees them together and merges natively. Both workarounds get deleted.

---

## 7. Schema changes

`academic_events`:
```
+ status                 ACTIVE | CANCELLED | SUPERSEDED   default ACTIVE
+ needs_review           bool default true, indexed
+ superseded_by_id       uuid fk academic_events.id
+ date_precision         EXACT | DAY_ONLY | UNKNOWN
+ source_raw_message_id  uuid fk raw_messages.id    (real FK; replaces String(255))
+ event_index            int default 0
+ revisions              jsonb                      (UPDATE audit trail)
~ embedding              String  ->  Vector(384) + HNSW index
+ UNIQUE (user_id, source_raw_message_id, event_index)
+ INDEX  (user_id, course_code, event_type, date_time)    <- business dedup key
```

`raw_messages`:
```
+ text_hash  String(64), indexed
~ ProcessingStatus += QUARANTINED, FILTERED_OUT, SKIPPED_EMPTY, SKIPPED_FRAGMENT, SKIPPED_REPEAT
```

The unique constraint is what makes duplicate-on-reprocess structurally impossible rather than "hopefully caught by cosine ≥ 0.88".

---

## 8. Files: expected delta

| File | Now | After |
|---|---|---|
`whatsapp_listener_service.py` | 448 L — polls + classifies + extracts + dedupes + notifies | ~330 L — polls + persists + coverage state machine. **The coverage/backoff/bot-removal logic is the best code in the pipeline; leave it alone.** |
`classifier_service.py` | 337 L | ~60 L — enums + prefilter constants |
`semantic_classifier.py` | 332 L | **delete** |
`setfit_classifier_service.py` | runtime tier that silently never loads | move to `training/`, offline eval only |
`event_extraction_service.py` | 525 L | ~180 L — `EventNormalizer` only |
`temporal_parser.py` | 179 L | ~260 L — this one **grows** |
`agnes_service.py` | 2 prompts, batch unused on hot path | 1 prompt, batch is the only path |
`deduplication_service.py` | O(n) Python cosine | business key → pgvector HNSW |
`scheduler._run_ai_chat_batch_parse` | 3rd writer | **delete** |
`process_agnes_batch_task` | 2nd writer, no dedup | **delete** (folded into the one path) |

Net ≈ **−1,200 / +400 lines**.

---

## 9. Worked example

Message, Fri 21 Aug 2026 10:14, group "EEE 300L":

> "Good morning everyone. Please note that the ELE 310 CA test earlier fixed for Monday has been moved to Friday 2pm, Hall B."

**Now:** title `"[ELE310] Good morning everyone"` (first line); weekday scan hits `monday` before `friday` → `date_time = Mon 24 Aug 09:00`; `has_moved` → `event_type = ALERT`, so not even a deadline; `urgency = 0.5`; `action_type` dropped → new row, original Monday test untouched with its reminder still armed. 30 min later Agnes writes a **second** row with `source_message_id = NULL`. User sees two cards, one with the wrong date.

**After:** prefilter passes → Agnes returns `{action_type: "UPDATE", category: "DEADLINE", course_code: "ELE 310", title: "ELE310 CA test moved to Friday 2pm", venue: "Hall B", date_expression: "friday 2pm", date_is_explicit: true}` → normalizer: `ELE310`, `resolve("friday 2pm", anchor=Fri 21 Aug 10:14)` → **Fri 21 Aug 14:00, EXACT** (2pm today is still ahead) → reconcile `UPDATE` on business key → patches the existing Monday row, appends a revision, cancels the Monday reminder, arms the new one → urgency ≈ 0.94, top of dashboard → one card: **"ELE310 CA test — today 2:00 PM, Hall B · Updated 2 min ago · from EEE 300L"** with a confirm chip.

---

## 10. Expected effect

| | Now | After |
|---|---|---|
Agnes calls per message | ~5 | ~0.07 (1 per 15) |
SetFit inferences per message | up to 4 | 0 until deliberately reintroduced |
Embeddings per event | 3, from 3 different base strings | 1, one contract |
Writers to `academic_events` | 3 | 1 |
Dedup cost | full 30-day scan + Python loop | indexed lookup + one HNSW query |
Duplicate cards on reprocess | routine | blocked by unique constraint |
Cancellations | create a second card | cancel original + kill reminder |
Worst-case latency | 30 min | 90 s (immediate on tripwire) |
Batch API failure | up to 50 messages lost silently | retry → bisect → quarantine |
Dashboard ordering | keyword-driven | deadline-driven |

---

## 11. Implementation order

1. **P0 correctness** — §2.1 `needs_review` column, §2.2 `ProcessingStatus` members, §2.3 dead `Event` import, §2.4 `action_type` passthrough, §2.5 batch-failure handling. Small, local, no architecture change. Stops active data loss.
2. **Collapse to one writer** — delete `scheduler._run_ai_chat_batch_parse` and `process_agnes_batch_task`; route the listener through the batch path. Biggest reduction in duplicate rows and API spend.
3. **Batch triggers + failure handling** — §6.1, §6.3.
4. **Temporal rewrite + `date_expression` prompt change** — behind a flag, with a fixture suite of real group messages so the change is measurable.
5. **Schema migration** — unique constraint, business-key index, pgvector.
6. **Derived urgency** — §6.5.
7. **Confirm chip + `trainingApi` binding + provenance in the UI** — §4.

Steps 1–2 are roughly a day and fix most visible damage. Steps 4–7 are where quality actually becomes good.

---

## 12. Constraints to respect (from AGENTS.md)

Knowtis is primarily a native Android/iOS app via Capacitor. Use `@capacitor/push-notifications` and `@capacitor/local-notifications` — never Web Notification APIs or Web Push service workers. Any dashboard work needs safe-area insets and 48×48 px minimum touch targets, and must keep the floating `BottomNav`.
