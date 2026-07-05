"""
Event Extraction Service
Extracts conservative academic event candidates from natural language text.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from app.services.classifier_service import MessageClassifier, ClassifierCategory, EventCategory, CATEGORY_MAP
from app.services.ner_service import NERService
from app.services.temporal_parser import TemporalParser
from app.services.llm_service import LLMService
from app.services.confidence_scorer import ConfidenceScorer

logger = logging.getLogger(__name__)


class EventExtractionService:
    """Service to parse raw message text and extract structured academic events."""

    @staticmethod
    def extract_event(
        text: str,
        db: Optional[Session] = None,
        msg_created_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parses raw text and extracts event metadata.
        Uses local classification, NER, and temporal parsing. SRL/LLM are deliberately
        kept off the default path to avoid overconfident extraction from chat fragments.
        """
        if not text or not text.strip():
            return None

        clean_text = text.strip()

        local_category, class_conf = MessageClassifier.classify_local_category(clean_text)
        classifier_cat = MessageClassifier.category_to_classifier(local_category)
        
        # If it's classified as noise, we shouldn't extract an event
        if classifier_cat == ClassifierCategory.NOISE:
            logger.debug("Event extraction skipped: message classified as noise")
            return None

        _, event_category = CATEGORY_MAP[classifier_cat]
        event_type = event_category.value

        scores = MessageClassifier.calculate_scores(clean_text)

        entities = NERService.extract_entities(clean_text, db)
        course_code = entities.get("course_code")
        venue = entities.get("location")
        lecturer = entities.get("lecturer")

        # Parse relative date relative to message timestamp
        date_time = TemporalParser.parse_date_time(clean_text, msg_created_at)
        has_date_reference = TemporalParser.has_date_reference(clean_text)

        # Determine title & description
        lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
        title = lines[0] if lines else "Academic Update"
        if course_code:
            course_title = entities.get("course_title")
            if course_title:
                title = f"[{course_code}] {course_title}: {title}"
            else:
                title = f"[{course_code}] {title}"

        if len(title) > 80:
            title = title[:77] + "..."
        description = clean_text

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
            llm_extracted = EventExtractionService._extract_via_llm(clean_text, msg_created_at)
            if llm_extracted:
                course_code = llm_extracted.get("course_code") or course_code
                event_type = llm_extracted.get("event_type") or event_type
                title = llm_extracted.get("title") or title
                description = llm_extracted.get("description") or description
                venue = llm_extracted.get("venue") or venue
                if llm_extracted.get("date_time"):
                    try:
                        date_time = datetime.fromisoformat(llm_extracted["date_time"].replace("Z", "+00:00"))
                        # Ensure we store naive UTC
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
        if event_type in {EventCategory.DEADLINE.value, EventCategory.ALERT.value} and not course_code:
            return "missing_course"
        if event_type in {EventCategory.DEADLINE.value, EventCategory.EVENT.value} and not date_time:
            return "missing_date" if not has_date_reference else "missing_time_resolution"
        return "complete"

    @staticmethod
    def _extract_via_llm(text: str, anchor_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Invokes Groq LLM to extract structured JSON data from the message."""
        import asyncio
        from app.timezone_utils import now_app
        
        anchor_str = anchor_time.isoformat() if anchor_time else now_app().isoformat()
        
        system_prompt = (
            "You are an expert academic information extraction system. "
            "Given a WhatsApp message from a student group and a Reference Timestamp, "
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

        user_content = f"Reference Timestamp: {anchor_str}\nMessage Text:\n{text}"
        
        try:
            # Run the async chat call synchronously
            from app.services.srl_service import _run_async
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
