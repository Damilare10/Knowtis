"""
AI Catch-Up Agent service.

Two layers:
  * Deterministic engine - retrieves relevant events, reminders, notifications
    and OCR output via the existing search/reminder/notification services and
    composes a structured, cited answer WITHOUT any LLM. Used as the fallback
    when Groq is unavailable and as the grounding context for the LLM.
  * Conversational layer - hands the retrieved context to the Groq LLM
    (``LLMService``) to produce a natural-language answer. Applied to BOTH
    free and premium tiers; free is capped at 10k received tokens elsewhere.

The retrieval step is shared: conversational queries reuse the deterministic
context as the LLM's grounding source, with citations bound to event IDs.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AcademicEvent, EventType, NotificationInbox, OCRExtraction, Reminder
from app.services.llm_service import LLMService
from app.services.reminder_service import ReminderService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

_COURSE_RE = re.compile(r"\b([a-z]{2,4})\s?(\d{3})\b")

_TYPE_KEYWORDS: Dict[str, List[str]] = {
    EventType.DEADLINE.value: [
        "assignment", "assign", "submit", "submission", "due", "deadline",
        "homework", "coursework", "project", "report", "quiz", "test",
        "exam", "ca", "assessment", "midsem", "mid-sem", "final",
    ],
    EventType.EVENT.value: [
        "class", "lecture", "venue", "where", "location", "room", "hall",
        "timetable", "schedule", "session", "practical", "lab", "tutorial",
    ],
    EventType.ALERT.value: [
        "cancel", "cancelled", "postpone", "postponed", "moved", "rescheduled",
        "shifted", "change", "changed", "reminder", "alert", "update",
    ],
    EventType.INFO.value: [
        "announce", "announcement", "notice", "info", "information",
        "general", "update",
    ],
}


@dataclass
class RetrievalContext:
    query: str
    intent: Dict
    events: List[AcademicEvent] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)
    notifications: List[NotificationInbox] = field(default_factory=list)
    ocr_extractions: List[OCRExtraction] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    @property
    def events_count(self) -> int:
        return len(self.events)

    @property
    def reminders_count(self) -> int:
        return len(self.reminders)

    @property
    def notifications_count(self) -> int:
        return len(self.notifications)

    @property
    def ocr_count(self) -> int:
        return len(self.ocr_extractions)


class AIAgentService:
    """Deterministic retrieval + composition, with an LLM upgrade path."""

    @staticmethod
    def parse_intent(query: str, course_code: Optional[str] = None) -> Dict:
        q = (query or "").lower()
        intent: Dict = {
            "course_code": course_code,
            "date_window": None,
            "event_types": [],
            "kind": "general",
        }

        if not intent["course_code"]:
            match = _COURSE_RE.search(q)
            if match:
                intent["course_code"] = (match.group(1) + match.group(2)).upper()

        if "tomorrow" in q or "tmrw" in q:
            intent["date_window"] = "tomorrow"
        elif "today" in q or "tonight" in q:
            intent["date_window"] = "today"
        elif "next week" in q:
            intent["date_window"] = "next_week"
        elif "this week" in q or "this wk" in q:
            intent["date_window"] = "week"
        elif "overdue" in q or "missed" in q or "past due" in q:
            intent["date_window"] = "overdue"
        elif "upcoming" in q or "soon" in q or "next" in q:
            intent["date_window"] = "upcoming"

        for event_type, keywords in _TYPE_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                intent["event_types"].append(EventType(event_type))

        # Include alerts if event or deadline is queried (e.g. rescheduling of a class/assignment)
        if intent["event_types"] and (EventType.EVENT in intent["event_types"] or EventType.DEADLINE in intent["event_types"]):
            if EventType.ALERT not in intent["event_types"]:
                intent["event_types"].append(EventType.ALERT)

        if any(k in q for k in ("remind", "reminder")):
            intent["kind"] = "reminders"
        elif any(k in q for k in ("notification", "unread", "inbox", "miss", "catch up", "catchup")):
            intent["kind"] = "notifications"
        elif any(k in q for k in ("timetable", "schedule", "screenshot", "image", "ocr", "photo")):
            intent["kind"] = "ocr"

        return intent

    @staticmethod
    def _date_bounds(window: Optional[str]):
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if window == "today":
            return today_start, today_start + timedelta(days=1)
        if window == "tomorrow":
            return today_start + timedelta(days=1), today_start + timedelta(days=2)
        if window == "week":
            return today_start, today_start + timedelta(days=7)
        if window == "next_week":
            return today_start + timedelta(days=7), today_start + timedelta(days=14)
        if window == "overdue":
            return None, now
        return None, None

    @staticmethod
    def retrieve(
        query: str,
        user_id,
        db: Session,
        course_code: Optional[str] = None,
    ) -> RetrievalContext:
        """Gather all relevant context for a user query (shared by both tiers)."""
        intent = AIAgentService.parse_intent(query, course_code)
        sources: List[str] = []

        semantic = SearchService.search_events(
            user_id, query, db, limit=25
        )
        if semantic:
            sources.append("semantic_search")

        semantic_events = [event for event, _ in semantic]
        intent_events = AIAgentService._filter_events(semantic_events, intent)
        if intent_events:
            events = intent_events
        elif semantic_events:
            events = semantic_events[:8]
        else:
            events = AIAgentService._fallback_query(intent, db, user_id)
        if events:
            sources.append("events")
        events = AIAgentService._rank_and_trim(events, intent)

        reminders = ReminderService.get_user_reminders(
            user_id, active_only=True, limit=20, db=db
        )
        if reminders:
            sources.append("reminders")

        try:
            notifications = (
                db.query(NotificationInbox)
                .filter(
                    NotificationInbox.user_id == user_id,
                    NotificationInbox.is_read == False,
                )
                .order_by(NotificationInbox.created_at.desc())
                .limit(10)
                .all()
            )
        except Exception as exc:
            logger.warning(f"Failed to load notifications: {exc}")
            notifications = []
        if notifications:
            sources.append("notifications")

        try:
            ocr_extractions = (
                db.query(OCRExtraction)
                .filter(OCRExtraction.user_id == user_id)
                .order_by(OCRExtraction.created_at.desc())
                .limit(5)
                .all()
            )
        except Exception as exc:
            logger.warning(f"Failed to load OCR extractions: {exc}")
            ocr_extractions = []
        if ocr_extractions:
            sources.append("ocr")

        if intent["kind"] == "notifications":
            reminders = []
        elif intent["kind"] == "reminders":
            notifications = []

        return RetrievalContext(
            query=query,
            intent=intent,
            events=events,
            reminders=reminders,
            notifications=notifications,
            ocr_extractions=ocr_extractions,
            sources=list(dict.fromkeys(sources)),
        )

    @staticmethod
    def _filter_events(
        events: List[AcademicEvent], intent: Dict
    ) -> List[AcademicEvent]:
        start, end = AIAgentService._date_bounds(intent.get("date_window"))
        types = intent.get("event_types") or []

        def matches(event: AcademicEvent) -> bool:
            if intent["course_code"] and (event.course_code or "").upper().replace(" ", "") != intent["course_code"]:
                return False
            if types and event.event_type not in types:
                return False
            if start and end:
                if not event.date_time:
                    return False
                if intent.get("date_window") == "overdue":
                    return event.date_time < end
                return start <= event.date_time < end
            if intent.get("date_window") == "upcoming" and event.date_time:
                return event.date_time >= datetime.utcnow()
            return True

        filtered = [e for e in events if matches(e)]
        return filtered

    @staticmethod
    def _fallback_query(intent: Dict, db: Session, user_id) -> List[AcademicEvent]:
        """Intent-filtered DB query used when semantic search yields nothing."""
        try:
            query = db.query(AcademicEvent).filter(
                AcademicEvent.user_id == user_id,
                AcademicEvent.is_archived == False,
                or_(
                    AcademicEvent.is_duplicate == False,
                    AcademicEvent.is_duplicate == None,
                ),
            )
            if intent.get("course_code"):
                from sqlalchemy import func
                clean_code = intent["course_code"].replace(" ", "").upper()
                query = query.filter(
                    func.replace(AcademicEvent.course_code, " ", "").ilike(f"%{clean_code}%")
                )
            if intent.get("event_types"):
                query = query.filter(
                    AcademicEvent.event_type.in_(intent["event_types"])
                )

            start, end = AIAgentService._date_bounds(intent.get("date_window"))
            window = intent.get("date_window")
            if window == "overdue":
                query = query.filter(AcademicEvent.date_time < end)
            elif start and end:
                query = query.filter(
                    AcademicEvent.date_time >= start,
                    AcademicEvent.date_time < end,
                )
            elif window == "upcoming":
                query = query.filter(AcademicEvent.date_time >= datetime.utcnow())

            return query.order_by(AcademicEvent.date_time.asc()).limit(25).all()
        except Exception as exc:
            logger.error(f"Fallback event query failed: {exc}")
            return []

    @staticmethod
    def _rank_and_trim(events: List[AcademicEvent], intent: Dict) -> List[AcademicEvent]:
        now = datetime.utcnow()

        def proximity(event: AcademicEvent) -> float:
            if not event.date_time:
                return 0.0
            delta = abs((event.date_time - now).total_seconds())
            return max(0.0, 1.0 - (delta / (14 * 24 * 3600)))

        def key(event: AcademicEvent):
            type_bonus = 0.25 if intent.get("event_types") and event.event_type in intent["event_types"] else 0.0
            return -(proximity(event) + type_bonus)

        return sorted(events, key=key)[:8]

    @staticmethod
    def compose_deterministic(ctx: RetrievalContext) -> Dict:
        """Rule-based answer with citations (no LLM)."""
        lines: List[str] = []
        intent = ctx.intent

        if intent["kind"] == "notifications" and ctx.notifications:
            lines.append(f"You have {ctx.notifications_count} unread notification(s).")
            for n in ctx.notifications[:6]:
                when = n.created_at.strftime("%d %b, %H:%M") if n.created_at else "recently"
                lines.append(f"  - {n.title or 'Notification'} ({when})")
        elif intent["kind"] == "reminders" and ctx.reminders:
            lines.append(f"You have {ctx.reminders_count} active reminder(s).")
            for r in ctx.reminders[:6]:
                when = r.scheduled_time.strftime("%a %d %b, %H:%M") if r.scheduled_time else "unscheduled"
                title = r.event.title if r.event else "an event"
                lines.append(f"  - {title} - reminds {when}")
        else:
            header = AIAgentService._header(intent)
            lines.append(header)
            if ctx.events:
                for event in ctx.events[:6]:
                    lines.append(AIAgentService._format_event(event))
            else:
                lines.append("No matching events found for that query.")

        if ctx.ocr_extractions and (intent["kind"] == "ocr" or not ctx.events):
            lines.append("")
            lines.append(f"OCR notes available: {ctx.ocr_count} extracted image(s).")
            for ocr in ctx.ocr_extractions[:3]:
                preview = (ocr.extracted_text or "").strip().replace("\n", " ")
                if len(preview) > 120:
                    preview = preview[:117] + "..."
                lines.append(f"  - {preview}")

        if ctx.events:
            lines.append("")
            lines.append(
                f"Sources: {ctx.events_count} event(s)"
                + (f", {ctx.reminders_count} reminder(s)" if ctx.reminders else "")
                + (f", {ctx.notifications_count} notification(s)" if ctx.notifications else "")
                + "."
            )

        answer = "\n".join(lines)
        return {
            "answer": answer,
            "citations": AIAgentService._citations(ctx.events),
            "retrieval": AIAgentService._retrieval_info(ctx),
        }

    @staticmethod
    def _header(intent: Dict) -> str:
        window = intent.get("date_window")
        course = intent.get("course_code")
        when = {
            "today": "today",
            "tomorrow": "tomorrow",
            "week": "this week",
            "next_week": "next week",
            "overdue": "overdue",
            "upcoming": "upcoming",
        }.get(window, "relevant")
        scope = f" for {course}" if course else ""
        return f"Here's what's {when}{scope}:"

    @staticmethod
    def _format_event(event: AcademicEvent) -> str:
        when = (
            event.date_time.strftime("%a %d %b, %H:%M")
            if event.date_time
            else "unscheduled"
        )
        course = f"[{event.course_code}] " if event.course_code else ""
        venue = f" at {event.venue}" if event.venue else ""
        etype = event.event_type.value if event.event_type else "EVENT"
        return f"  - {course}{event.title} - {when}{venue} ({etype})"

    @staticmethod
    def _citations(events: List[AcademicEvent]) -> List[Dict]:
        citations = []
        for event in events[:6]:
            citations.append(
                {
                    "event_id": event.id,
                    "title": event.title,
                    "course_code": event.course_code,
                    "date_time": event.date_time,
                    "event_type": event.event_type.value if event.event_type else None,
                    "venue": event.venue,
                }
            )
        return citations

    @staticmethod
    def _retrieval_info(ctx: RetrievalContext) -> Dict:
        return {
            "events_count": ctx.events_count,
            "reminders_count": ctx.reminders_count,
            "notifications_count": ctx.notifications_count,
            "ocr_count": ctx.ocr_count,
            "sources": ctx.sources,
        }

    @staticmethod
    def build_system_prompt(ctx: RetrievalContext) -> str:
        """Grounding prompt assembled from the deterministic retrieval step."""
        blocks: List[str] = [
            "You are Knowtis, a calm and concise academic catch-up assistant.",
            "Answer the student's question using ONLY the retrieved context below.",
            "When you reference an item, mention its course code and title.",
            "If the context is insufficient, say so briefly and suggest a concrete next step.",
            "Do not invent events, dates, or venues.",
            "",
            "RETRIEVED EVENTS:",
        ]
        if ctx.events:
            for event in ctx.events:
                when = event.date_time.isoformat() if event.date_time else "unscheduled"
                blocks.append(
                    f"- id={event.id} [{event.course_code or 'N/A'}] "
                    f"{event.title} | {when} | "
                    f"venue={event.venue or 'N/A'} | "
                    f"type={event.event_type.value if event.event_type else 'EVENT'}"
                )
        else:
            blocks.append("(none)")

        blocks.append("")
        blocks.append("ACTIVE REMINDERS:")
        if ctx.reminders:
            for r in ctx.reminders:
                when = r.scheduled_time.isoformat() if r.scheduled_time else "unscheduled"
                title = r.event.title if r.event else "an event"
                blocks.append(f"- {title} (reminds {when})")
        else:
            blocks.append("(none)")

        blocks.append("")
        blocks.append("UNREAD NOTIFICATIONS:")
        if ctx.notifications:
            for n in ctx.notifications:
                blocks.append(f"- {n.title or 'Notification'}")
        else:
            blocks.append("(none)")

        if ctx.ocr_extractions:
            blocks.append("")
            blocks.append("OCR NOTES:")
            for ocr in ctx.ocr_extractions:
                preview = (ocr.extracted_text or "").strip().replace("\n", " ")
                blocks.append(f"- {preview[:300]}")

        return "\n".join(blocks)

    @staticmethod
    async def answer_premium(ctx: RetrievalContext, tier: str = "premium") -> Dict:
        """Conversational answer grounded in the retrieved context."""
        messages = [
            {"role": "system", "content": AIAgentService.build_system_prompt(ctx)},
            {"role": "user", "content": ctx.query},
        ]
        answer = await LLMService.chat(messages, tier=tier)
        return {
            "answer": answer,
            "citations": AIAgentService._citations(ctx.events),
            "retrieval": AIAgentService._retrieval_info(ctx),
        }
