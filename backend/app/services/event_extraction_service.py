"""
Event Extraction Service
Extracts conservative academic event candidates from natural language text.

Supports both single-event and multi-event extraction per message via Agnes AI with structured outputs.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.config import settings
from app.services.classifier_service import MessageClassifier, ClassifierCategory, EventCategory, CATEGORY_MAP
from app.services.ner_service import NERService
from app.services.temporal_parser import TemporalParser
from app.services.llm_service import LLMService
from app.services.confidence_scorer import ConfidenceScorer

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

    @staticmethod
    def extract_events(
        text: str,
        db: Optional[Session] = None,
        msg_created_at: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts all candidate academic events from a message text.
        Supports multi-event extraction per single message.
        """
        if not text or not text.strip():
            return []

        try:
            from app.services.agnes_service import AgnesService
            from app.tasks import _run_async

            raw_res = _run_async(AgnesService.classify_and_extract(text.strip(), msg_created_at))
            if raw_res and raw_res.get("classification") == "SIGNAL":
                events_list = raw_res.get("events") or []
                wrapped_list = []
                for ev_item in events_list:
                    wrapped = EventExtractionService._wrap_batch_result(ev_item, db=db)
                    if wrapped:
                        wrapped_list.append(wrapped)
                if wrapped_list:
                    return wrapped_list
        except Exception as exc:
            logger.debug("Agnes multi-event extraction fallback to single pipeline: %s", exc)

        single = EventExtractionService.extract_event(text, db, msg_created_at)
        return [single] if single else []

    @staticmethod
    # DEPRECATED: no production caller as of step 2; removed in step 4.
    def extract_event(
        text: str,
        db: Optional[Session] = None,
        msg_created_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parses raw text and extracts primary event metadata using legacy/hybrid pipeline.
        """
        if not text or not text.strip():
            return None

        return EventExtractionService._extract_legacy(text.strip(), db, msg_created_at)

    @staticmethod
    # DEPRECATED: no production caller as of step 2; removed in step 4.
    def _extract_legacy(
        text: str,
        db: Optional[Session] = None,
        msg_created_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:

        if EventExtractionService._is_peer_question_or_non_event(text):
            logger.debug("Event extraction skipped: message is peer inquiry/chatter: %r", text[:120])
            return None

        local_category, class_conf = MessageClassifier.classify_local_category(text)
        classifier_cat = MessageClassifier.category_to_classifier(local_category)

        if classifier_cat == ClassifierCategory.NOISE:
            logger.debug("Event extraction skipped: message classified as noise")
            return None

        if EventExtractionService._is_bare_fragment(text, classifier_cat):
            logger.debug("Event extraction skipped: message is a bare fragment with no substance: %r", text[:120])
            return None

        _, event_category = CATEGORY_MAP[classifier_cat]
        event_type = event_category.value

        scores = MessageClassifier.calculate_scores(text)

        entities = NERService.extract_entities(text, db)
        course_code = EventExtractionService.align_course_code(entities.get("course_code"), db)
        venue = entities.get("location")
        lecturer = entities.get("lecturer")

        date_time = TemporalParser.parse_date_time(text, msg_created_at)
        has_date_reference = TemporalParser.has_date_reference(text)

        lines = [ll.strip() for ll in text.splitlines() if ll.strip()]
        title = lines[0] if lines else "Academic Update"
        if course_code:
            title = f"[{course_code}] {title}"
        if len(title) > 80:
            title = title[:77] + "..."
        description = text

        actionability = EventExtractionService._assess_actionability(
            event_type=event_type,
            course_code=course_code,
            date_time=date_time,
            has_date_reference=has_date_reference,
        )
        event_completeness = EventExtractionService._event_completeness(
            event_type=event_type,
            course_code=course_code,
            date_time=date_time,
            has_date_reference=has_date_reference,
        )

        is_uncertain = actionability != "noise" and event_completeness != "complete"

        if is_uncertain and LLMService.is_available():
            logger.info("Local extraction uncertain. Triggering LLM extraction fallback.")
            llm_extracted = EventExtractionService._extract_via_llm(text, msg_created_at)
            if llm_extracted:
                course_code = EventExtractionService.align_course_code(llm_extracted.get("course_code") or course_code, db)
                event_type = llm_extracted.get("event_type") or event_type
                title = llm_extracted.get("title") or title
                description = llm_extracted.get("description") or description
                venue = llm_extracted.get("venue") or venue
                if llm_extracted.get("date_time"):
                    try:
                        date_time = datetime.fromisoformat(llm_extracted["date_time"].replace("Z", "+00:00"))
                        if date_time.tzinfo is not None:
                            date_time = date_time.astimezone(timezone.utc).replace(tzinfo=None)
                    except ValueError:
                        pass
                has_date_reference = has_date_reference or bool(llm_extracted.get("date_time"))
                event_completeness = EventExtractionService._event_completeness(
                    event_type=event_type,
                    course_code=course_code,
                    date_time=date_time,
                    has_date_reference=has_date_reference,
                )
                actionability = EventExtractionService._assess_actionability(
                    event_type=event_type,
                    course_code=course_code,
                    date_time=date_time,
                    has_date_reference=has_date_reference,
                )
                scores["confidence_score"] = min(scores["confidence_score"] + 0.08, 0.95)

        entity_clarity = ConfidenceScorer.evaluate_entity_clarity(course_code, date_time, venue)
        confidence_score = ConfidenceScorer.calculate_confidence(
            evidence_count=1,
            source_reliability=0.8,
            entity_clarity=entity_clarity,
            model_confidence=scores["confidence_score"],
        )
        if event_completeness != "complete":
            confidence_score = min(confidence_score, 0.74)

        field_confidence = ConfidenceScorer.field_confidences(
            course_code=course_code,
            date_time=date_time,
            venue=venue,
            classification_confidence=class_conf,
        )

        return {
            "course_code": course_code,
            "event_type": event_type,
            "academic_category": local_category,
            "title": title,
            "description": description,
            "venue": venue,
            "date_time": date_time,
            "lecturer": lecturer,
            "actionability": actionability,
            "event_completeness": event_completeness,
            "field_confidence": field_confidence,
            "needs_review": event_completeness != "complete" or confidence_score < 0.85,
            "urgency_score": scores["urgency_score"],
            "confidence_score": confidence_score,
            "relevance_score": scores["relevance_score"],
            "actionability_score": scores["actionability_score"],
        }

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

            nested_events = item.get("events")
            if nested_events:
                for ev_item in nested_events:
                    wrapped = EventExtractionService._wrap_batch_result(ev_item, db=db)
                    if wrapped:
                        results.append(wrapped)
            else:
                wrapped = EventExtractionService._wrap_batch_result(item, db=db)
                if wrapped:
                    results.append(wrapped)

        return results

    @staticmethod
    def _wrap_batch_result(agnes: Dict[str, Any], db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Convert a single Agnes batch result item to the standardized event dict.
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

        date_time = None
        date_time_str = agnes.get("date_time")
        if date_time_str:
            try:
                date_time = datetime.fromisoformat(
                    date_time_str.replace("Z", "+00:00")
                )
                if date_time.tzinfo is not None:
                    date_time = date_time.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError):
                logger.debug("Failed to parse Agnes date_time: %s", date_time_str)

        urgency = agnes.get("urgency_score", 0.5)
        confidence = agnes.get("confidence_score", 0.8)
        relevance = agnes.get("relevance_score", 0.7)
        actionability_score = agnes.get("actionability_score", 0.6)
        needs_review = agnes.get("needs_review", False)
        event_completeness = agnes.get("event_completeness", "complete")

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

        title = agnes.get("title", "Academic Update") or "Academic Update"
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
            "lecturer": agnes.get("lecturer"),
            "actionability": actionability,
            "event_completeness": event_completeness,
            "field_confidence": field_confidence,
            "needs_review": needs_review,
            "urgency_score": urgency,
            "confidence_score": confidence,
            "relevance_score": relevance,
            "actionability_score": actionability_score,
        }

    # ──────────────────────────────────────────────────────────────
    #  Noise & Fragment detection (works for both paths)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _is_peer_question_or_non_event(text: str) -> bool:
        """
        Detects casual student questions, borrowing requests, peer inquiries, and banter.
        """
        if not text:
            return True
        t_low = text.lower().strip()
        peer_patterns = [
            r"^(?:who\s+(?:has|have|is|knows)|has\s+anyone|anyone\s+(?:seen|have|knows|with)|can\s+someone|does\s+anyone)",
            r"^(?:please\s+who|pls\s+who|where\s+(?:is|are|the)|are\s+we\s+having|is\s+there\s+any|is\s+class\s+holding)",
            r"^(?:did\s+anyone|has\s+the\s+lecturer|any\s+update\s+on|good\s+morning|good\s+afternoon|good\s+evening)",
            r"\b(?:i\s+need\s+to\s+borrow|borrow\s+(?:me\s+)?(?:the\s+)?(?:textbook|slides?|notes?|pdf|past\s+questions?))\b",
            r"\b(?:who\s+has\s+the\s+textbook|anyone\s+seen\s+the\s+lecturer|seen\s+the\s+lecturer\?)\b",
            r"\b(?:where\s+are\s+you\s+guys|are\s+you\s+guys\s+in\s+class|is\s+anyone\s+in\s+class)\b",
        ]
        if any(re.search(p, t_low) for p in peer_patterns):
            official_keywords = [
                "assignment is due", "submission deadline", "class is cancelled",
                "lecture is cancelled", "rescheduled to", "venue changed to", "exam timetable"
            ]
            if not any(okw in t_low for okw in official_keywords):
                return True
        if t_low.endswith("?") and not any(kw in t_low for kw in ("deadline", "assignment", "exam", "test", "cancel", "venue")):
            return True
        return False

    @staticmethod
    # DEPRECATED: no production caller as of step 2; only caller is _extract_legacy. Removed in step 4.
    def _is_bare_fragment(text: str, classifier_cat: "ClassifierCategory") -> bool:
        stripped = text.strip()
        words = stripped.split()
        if not words:
            return True

        if len(words) <= 3:
            action_keywords = (
                "cancelled", "cancel", "postponed", "rescheduled",
                "moved", "shifted", "venue change", "new venue",
                "deadline", "due", "exam", "quiz", "test", "closed",
                "lecture", "class", "lab", "tutorial", "assessment",
                "assignment", "homework", "submission", "project",
            )
            has_action = any(kw in stripped.lower() for kw in action_keywords)

            if classifier_cat == ClassifierCategory.NOISE and not has_action:
                return True
            if classifier_cat == ClassifierCategory.INFO and not has_action:
                return True
            if classifier_cat in (
                ClassifierCategory.DEADLINE,
                ClassifierCategory.EVENT,
                ClassifierCategory.ALERT,
            ) and not has_action:
                return True

        temporal_pattern = re.compile(
            r"\b("
            r"tomorrow|today|day\s+after\s+tomorrow"
            r"|\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?"
            r"|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
            r"|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?"
            r"|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?"
            r"|next\s+(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:rs(?:day)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
            r"|(?:this\s+)?(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:rs(?:day)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
            r"|\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?"
            r"|\d{1,2}:\d{2}(?:\s*(?:am|pm))?"
            r")\b",
            re.IGNORECASE,
        )
        stripped_of_time = temporal_pattern.sub("", stripped).strip()
        remaining_words = stripped_of_time.split()

        if not remaining_words:
            return True

        if len(remaining_words) == 1 and remaining_words[0].lower() in (
            "and", "or", "at", "by", "on", "in", "the", "a", "an", "to",
            "is", "was", "are",
        ):
            return True

        return False

    # ──────────────────────────────────────────────────────────────
    #  Utility helpers
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _assess_actionability(
        event_type: str,
        course_code: Optional[str],
        date_time: Optional[datetime],
        has_date_reference: bool,
    ) -> str:
        if event_type == EventCategory.INFO.value:
            return "needs_attention"
        if event_type == EventCategory.ALERT.value:
            return "update_existing_event" if course_code else "needs_attention"
        if event_type in {EventCategory.DEADLINE.value, EventCategory.EVENT.value}:
            return "schedule_reminder" if course_code and date_time else "needs_attention"
        return "needs_attention" if has_date_reference or course_code else "FYI"

    @staticmethod
    def _event_completeness(
        event_type: str,
        course_code: Optional[str],
        date_time: Optional[datetime],
        has_date_reference: bool,
    ) -> str:
        if event_type in {EventCategory.DEADLINE.value, EventCategory.ALERT.value}:
            if not course_code:
                return "missing_course"
        if event_type == EventCategory.EVENT.value:
            if not course_code:
                return "missing_course"
        if event_type in {EventCategory.DEADLINE.value, EventCategory.EVENT.value}:
            if not date_time:
                return "missing_date" if not has_date_reference else "missing_time_resolution"
        return "complete"

    @staticmethod
    def _extract_via_llm(text: str, anchor_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        from app.timezone_utils import now_app

        anchor_dt = anchor_time or now_app()
        weekday_name = anchor_dt.strftime("%A")
        anchor_str = f"{weekday_name}, {anchor_dt.isoformat()} (Day of week: {weekday_name})"

        system_prompt = (
            "You are an expert academic information extraction system. "
            "Given a WhatsApp message from a student group and a Reference Timestamp Anchor, "
            "extract the structured event details.\n\n"
            "Return a JSON object with these EXACT keys:\n"
            "- course_code: Normalized course code (e.g. 'CSC301', 'ELE310', uppercase, no spaces, or null)\n"
            "- event_type: One of: 'DEADLINE', 'EVENT', 'ALERT', 'INFO'\n"
            "- title: Clear summary of the announcement (max 80 chars, e.g. 'CSC301 Quiz postponed')\n"
            "- description: Full details or the raw text\n"
            "- venue: Location of event or null\n"
            "- date_time: Resolved ISO-8601 date-time string in UTC, calculated relative to the Reference Timestamp. "
            "If no time is specified, default to 09:00:00. If no date is specified, return null.\n\n"
            "Return ONLY the raw JSON object. Do not wrap in markdown or backticks."
        )

        user_content = f"Reference Timestamp Anchor: {anchor_str}\nMessage Text:\n{text}"

        try:
            from app.tasks import _run_async
            response_str = _run_async(LLMService.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0,
                max_tokens=250
            ))

            clean_response = response_str.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            return json.loads(clean_response)
        except Exception as e:
            logger.warning("LLM extraction fallback failed: %s", e)
            return None