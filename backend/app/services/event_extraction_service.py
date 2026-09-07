"""
Event Extraction Service

Wraps Agnes batch extraction results into the standardized event dict consumed
by the single batch writer (``app.tasks.process_message_batch``).

Dates are NOT resolved by the model: Agnes returns the temporal phrase as
written and ``TemporalParser.resolve`` does the arithmetic against each
message's own timestamp, so resolution is deterministic, testable and auditable.
"""
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.services.temporal_parser import DatePrecision, TemporalParser

logger = logging.getLogger(__name__)


class EventExtractionService:
    """Service to parse raw message text and extract structured academic events."""

    @staticmethod
    def canonical_dedup_text(event: dict) -> str:
        """Single source string for BOTH the stored vector and every query vector.

        Using one canonical form eliminates the §2.9 embedding mismatch where
        three writers built vectors from three different base strings while
        ``find_duplicate`` queried with a fourth.
        """
        return f"{event.get('event_type') or ''}|{event.get('course_code') or ''}|{event.get('title') or ''}"

    @staticmethod
    def align_course_code(course_code: Optional[str], db: Optional[Session] = None) -> Optional[str]:
        """
        Normalizes course code format (e.g. 'csc 301' -> 'CSC301') and performs
        fuzzy alignment against active database course codes if available.
        """
        if not course_code or not course_code.strip():
            return None

        cleaned = re.sub(r"[\s\-]+", "", course_code.strip().upper())
        if not cleaned:
            return None

        if db is not None:
            try:
                from app.models import AcademicEvent

                existing_codes = set()
                db_events = (
                    db.query(AcademicEvent.course_code)
                    .filter(AcademicEvent.course_code.isnot(None))
                    .distinct()
                    .limit(200)
                    .all()
                )
                for row in db_events:
                    if row[0]:
                        existing_codes.add(re.sub(r"[\s\-]+", "", row[0].upper()))

                if existing_codes and cleaned not in existing_codes:
                    import difflib
                    matches = difflib.get_close_matches(cleaned, list(existing_codes), n=1, cutoff=0.85)
                    if matches:
                        logger.info("Canonical course code aligned: %r -> %r", cleaned, matches[0])
                        return matches[0]
            except Exception as exc:
                # Surfaced at WARNING: a silent failure here means canonical
                # alignment is off and nobody knows it.
                logger.warning(
                    "Course code alignment against DB failed for %r: %s", cleaned, exc
                )

        return cleaned

    # ────────────────────────────────────────────
    #  Agnes batch extraction
    # ────────────────────────────────────────────

    @staticmethod
    def extract_batch_via_agnes(
        messages: List[Dict[str, Any]],
        msg_created_at: Optional[datetime] = None,
        db: Optional[Session] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Batch extraction via Agnes 2.0 Flash.

        Return contract — callers MUST distinguish these two cases, because one
        means "safe to mark the messages processed" and the other means "retry":

        * ``None``  -> the batch FAILED (network error, timeout, rate limit, or
          the model returned unparseable JSON). Nothing can be concluded about
          the messages; leave them unprocessed.
        * ``[]``    -> the batch SUCCEEDED and contained no academic events, i.e.
          every message was noise. Safe to mark processed.
        * non-empty -> the extracted events.
        """
        from app.services.agnes_service import AgnesService
        from app.tasks import _run_async

        try:
            raw_events = _run_async(
                AgnesService.classify_and_extract_batch(messages, msg_created_at)
            )
        except Exception as exc:
            logger.error(
                "Agnes batch extraction raised for %d message(s): %s",
                len(messages), exc, exc_info=True,
            )
            return None

        if raw_events is None:
            # AgnesService already logged the cause (HTTP failure or invalid JSON).
            return None

        results = []
        for item in raw_events:
            classification = (item.get("classification") or "").upper()
            if classification == "NOISE":
                continue

            # 1-based index of the source message within `messages`, per the
            # prompt contract. Threaded through so the writer can attribute each
            # event to the message that actually produced it instead of to the
            # batch head, and so each event resolves its date against its own
            # message timestamp.
            src_index = item.get("index")
            anchor = msg_created_at
            if isinstance(src_index, int) and 1 <= src_index <= len(messages):
                anchor = messages[src_index - 1].get("created_at") or msg_created_at

            nested_events = item.get("events")
            candidates = nested_events if nested_events else [item]
            for ev_item in candidates:
                wrapped = EventExtractionService._wrap_batch_result(
                    ev_item, db=db, anchor=anchor
                )
                if wrapped:
                    wrapped["_source_index"] = src_index
                    results.append(wrapped)

        return results

    # Titles that carry no information. A card showing one of these is worse than
    # no card: it occupies the feed, cannot be searched, and teaches the user that
    # extraction is unreliable. The batch prompt used to ship without any event
    # schema at all, so the model omitted `title` and the pydantic default turned
    # every single card into "Academic Update".
    _PLACEHOLDER_TITLES = {
        "", "academic update", "update", "updates", "announcement", "announcements",
        "notice", "info", "information", "n/a", "na", "none", "null", "untitled",
    }

    # Openers to skip when salvaging a title from the message body.
    _TITLE_SKIP_PREFIX = re.compile(
        r"^(?:@\w+\s*|good\s+(?:morning|afternoon|evening|day)\b|hello\b|hi\b|hey\b|"
        r"greetings\b|attention\b|please\s+note\b|kindly\s+note\b|note\b|"
        r"important\b|urgent\b|guys\b|everyone\b|all\b)[\s,:.!-]*",
        re.IGNORECASE,
    )

    @staticmethod
    def _resolve_title(agnes: Dict[str, Any]) -> str:
        """Return a usable title, salvaging from the description if needed.

        Returns "" when nothing usable exists, so the caller can drop the event
        instead of persisting a placeholder card.
        """
        title = (agnes.get("title") or "").strip()
        if title.lower().rstrip(".!") not in EventExtractionService._PLACEHOLDER_TITLES:
            return title[:80]

        # Salvage: take the first sentence of the description that still has
        # substance once the greeting/@mention opener is stripped.
        body = (agnes.get("description") or agnes.get("message_text") or "").strip()
        if not body:
            return ""

        for chunk in re.split(r"(?<=[.!?])\s+|\n+", body):
            candidate = EventExtractionService._TITLE_SKIP_PREFIX.sub("", chunk.strip()).strip()
            if len(candidate.split()) >= 3:
                logger.warning(
                    "Model omitted a usable title; salvaged %r from the description. "
                    "Check the extraction prompt.",
                    candidate[:80],
                )
                return candidate[:80]

        return ""

    @staticmethod
    def _wrap_batch_result(
        agnes: Dict[str, Any],
        db: Optional[Session] = None,
        anchor: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a single Agnes batch result item to the standardized event dict.

        ``anchor`` is that event's OWN source-message timestamp, not the batch
        head. A batch spans up to 15 messages and can cross midnight, so using
        one anchor for all of them resolves "tomorrow" to the wrong day.
        """
        event_type = (agnes.get("category") or "INFO").upper()
        if event_type not in ("DEADLINE", "EVENT", "ALERT", "INFO"):
            return None

        category_map = {
            "DEADLINE": "assignment_deadline",
            "EVENT": "event",
            "ALERT": "lecture_update",
            "INFO": "general_announcement",
        }
        academic_category = category_map.get(event_type, "general_announcement")

        raw_code = agnes.get("course_code")
        course_code = EventExtractionService.align_course_code(raw_code, db)

        # Dates are resolved HERE, deterministically, never by the model. The
        # model returns the phrase as written; TemporalParser does the
        # arithmetic against the message's own timestamp so it is testable and
        # auditable.
        if agnes.get("date_time"):
            logger.info(
                "Agnes returned a deprecated resolved date_time (%r); ignoring in "
                "favour of date_expression. The prompt should no longer ask for it.",
                agnes.get("date_time"),
            )

        date_time, date_precision = TemporalParser.resolve(
            agnes.get("date_expression"),
            anchor=anchor,
            explicit=bool(agnes.get("date_is_explicit")),
        )

        confidence = agnes.get("confidence_score", 0.8)
        relevance = agnes.get("relevance_score", 0.7)
        actionability_score = agnes.get("actionability_score", 0.6)
        needs_review = agnes.get("needs_review", False)
        event_completeness = agnes.get("event_completeness", "complete")

        # A resolved date the model did not commit to is weaker evidence, so a
        # non-explicit temporal phrase forces review.
        if date_precision == DatePrecision.UNKNOWN or not agnes.get("date_is_explicit"):
            if event_type in ("DEADLINE", "EVENT"):
                needs_review = True

        field_confidence = {
            "course_code": 0.85 if course_code else 0.2,
            "date_time": 0.85 if date_time else 0.3,
            "venue": 0.85 if agnes.get("venue") else 0.5,
        }

        if event_type == "INFO":
            actionability = "needs_attention"
        elif event_type == "ALERT":
            actionability = "update_existing_event"
        elif event_type in ("DEADLINE", "EVENT"):
            actionability = "schedule_reminder" if course_code and date_time else "needs_attention"
        else:
            actionability = "needs_attention"

        title = EventExtractionService._resolve_title(agnes)
        if not title:
            logger.error(
                "Dropping extracted event with no usable title (course=%r, category=%r). "
                "The model omitted `title` and nothing could be salvaged from the description.",
                course_code, event_type,
            )
            return None
        description = agnes.get("description") or agnes.get("message_text") or ""

        # action_type drives the UPDATE / CANCEL branches of
        # DeduplicationService.reconcile_event. Dropping it here made every
        # cancellation create a second card instead of cancelling the first.
        action_type = (agnes.get("action_type") or "CREATE").upper()
        if action_type not in ("CREATE", "UPDATE", "CANCEL"):
            logger.debug("Unrecognized Agnes action_type %r; defaulting to CREATE", action_type)
            action_type = "CREATE"

        return {
            "action_type": action_type,
            "course_code": course_code,
            "event_type": event_type,
            "academic_category": academic_category,
            "title": title,
            "description": description,
            "venue": agnes.get("venue"),
            "date_time": date_time,
            "date_precision": date_precision.value,
            "lecturer": agnes.get("lecturer"),
            "actionability": actionability,
            "event_completeness": event_completeness,
            "field_confidence": field_confidence,
            "needs_review": needs_review,
            # urgency_score is intentionally omitted: it is derived from
            # time-to-deadline by urgency_service, never taken from the model.
            "confidence_score": confidence,
            "relevance_score": relevance,
            "actionability_score": actionability_score,
        }
