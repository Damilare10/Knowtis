"""
Agnes AI Integration Service
Unified classification + multi-event extraction for WhatsApp messages using Agnes 2.0 Flash with Structured Outputs.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.schemas import SingleMessageAIResponse, BatchMessageAIResponse, ExtractedEventItem

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = (
    "You are an academic event extraction engine for Nigerian university WhatsApp groups. "
    "Given a message from a student group and a reference timestamp anchor, classify it and extract all structured academic events.\n\n"
    "RETURN ONLY a JSON object conforming strictly to this shape:\n"
    "{\n"
    '  "classification": "SIGNAL" or "NOISE",\n'
    '  "events": [\n'
    "    {\n"
    '      "action_type": "CREATE" | "UPDATE" | "CANCEL",\n'
    '      "category": "DEADLINE" | "EVENT" | "ALERT" | "INFO",\n'
    '      "course_code": "CSC301" or null,\n'
    '      "title": "Concise info card title (max 80 chars)",\n'
    '      "description": "Extracted event details with context",\n'
    '      "venue": "Location" or null,\n'
    '      "date_expression": "the temporal phrase EXACTLY as written in the message, e.g. \'next friday 2pm\', \'tomorrow\', \'30th\'" or null,\n'
    '      "date_is_explicit": true if the message states a date or day, false for vague wording like "soon",\n'
    '      "lecturer": "Lecturer name" or null,\n'
    '      "confidence_score": float 0.0-1.0,\n'
    '      "relevance_score": float 0.0-1.0,\n'
    '      "actionability_score": float 0.0-1.0,\n'
    '      "needs_review": boolean,\n'
    '      "event_completeness": "complete" | "missing_course" | "missing_date" | "missing_time_resolution"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "STRICT RULES:\n"
    "1. Greetings, jokes, memes, casual chat, student questions/inquiries (e.g. 'who has the textbook', 'has anyone seen the lecturer', 'can someone send slides', 'are we having class'), textbook/material borrowing requests, noted, ok, lol -> classification=NOISE, events=[]. A valid SIGNAL MUST be an actionable announcement, schedule update, test/exam, or assignment deadline, NOT a student question.\n"
    "2. action_type is REQUIRED on every event: 'CREATE' for new events/deadlines, 'UPDATE' for changes in venue/time/deadline extension, or 'CANCEL' for cancellations. It decides whether an existing card is patched or cancelled instead of a duplicate being created, so never omit it.\n"
    "2. Messages about assignments, exams, lecture changes, timetable updates -> classification=SIGNAL.\n"
    "3. Single messages may contain MULTIPLE distinct events (e.g. an assignment deadline AND a class cancellation). "
    "Extract EVERY valid event as an entry inside the `events` array.\n"
    "4. DO NOT compute, resolve, or convert dates. Copy the temporal phrase verbatim into date_expression "
    "('tomorrow', 'next friday 2pm', 'by the 30th'). Date resolution happens downstream against the message's own "
    "timestamp. Never output an ISO date and never guess a time that the message does not state.\n"
    "5. Normalize course codes: uppercase, no spaces (e.g. csc 301 -> CSC301).\n"
    "6. Do NOT output urgency_score; urgency is computed downstream from the deadline.\n"
    "7. Return ONLY valid JSON."
)


class AgnesService:
    """Agnes 2.0 Flash wrapper for classification + extraction.
    Uses OpenAI-compatible API endpoint at apihub.agnes-ai.com."""

    BATCH_PROMPT = (
        "You are an academic event extraction engine for Nigerian university WhatsApp groups.\n"
        "Given a list of numbered messages from a student group and a reference timestamp anchor, "
        "classify each message and extract structured event data.\n\n"
        "RETURN ONLY a JSON object with key 'items' containing an array of objects:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "index": 1,\n'
        '      "classification": "SIGNAL" or "NOISE",\n'
        '      "events": [\n'
        "        { ...event object adhering to standard schema... }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "STRICT RULES:\n"
        "1. Return ONE item per message. The `index` field is REQUIRED on every item and MUST equal the "
        "message number exactly as given. Never renumber, never omit it, never merge two messages into one item "
        "-- the index is how each extracted event is attributed back to its source message.\n"
        "2. If NOISE (casual chat, student questions like 'who has textbook', 'has anyone seen lecturer', material requests, greetings), classification=NOISE and events=[].\n"
        "3. If SIGNAL (official class announcement, assignment deadline, exam/quiz, venue change), extract ALL distinct academic events into the `events` array.\n"
        "4. Every event object MUST include \"action_type\": \"CREATE\" for a newly announced "
        "event or deadline, \"UPDATE\" when an existing event changes (rescheduled, postponed, "
        "moved, venue change, deadline extended), or \"CANCEL\" when an existing event is "
        "cancelled, called off, or will no longer hold. This field decides whether an existing "
        "card is patched or cancelled instead of a duplicate being created, so never omit it.\n"
        "5. DO NOT compute or resolve dates. Put the temporal phrase EXACTLY as written into "
        "\"date_expression\" ('tomorrow', 'next friday 2pm', 'by the 30th') and set "
        "\"date_is_explicit\" true only when the message names a date or day. Resolution happens "
        "downstream against each message's own timestamp. Never output an ISO date.\n"
        "6. Normalize course codes: 3-4 letters + 3-4 digits, no spaces, uppercase (e.g. CSC301).\n"
        "7. Do NOT output urgency_score; urgency is computed downstream from the deadline.\n"
        "8. Return ONLY valid JSON."
    )

    @staticmethod
    def _format_anchor_timestamp(msg_created_at: Optional[datetime] = None) -> str:
        """Formats anchor timestamp with explicit Day of Week for LLM date resolution."""
        from app.timezone_utils import now_app

        anchor = msg_created_at or now_app()
        if isinstance(anchor, datetime):
            anchor_utc = anchor.replace(tzinfo=anchor.tzinfo or timezone.utc)
            day_name = anchor_utc.strftime("%A")
            iso_str = anchor_utc.isoformat()
            return f"{day_name}, {iso_str} (Day of week: {day_name})"
        return str(anchor)

    @staticmethod
    async def classify_and_extract_batch(
        messages: List[Dict[str, Any]],
        msg_created_at: Optional[datetime] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Batch classification + extraction via Agnes 2.0 Flash.

        Args:
            messages: List of dicts with ``id`` and ``message_text`` keys.
            msg_created_at: Anchor timestamp for relative date parsing.

        Returns:
            List of extracted event dicts, or None on failure.
        """
        if not messages:
            return []

        anchor_str = AgnesService._format_anchor_timestamp(msg_created_at)

        numbered = []
        for i, msg in enumerate(messages, 1):
            text = msg.get("message_text") or ""
            numbered.append(f"Message {i}:\n{text}")
        msgs_block = "\n\n".join(numbered)

        user_content = (
            f"Reference Timestamp Anchor: {anchor_str}\n\n"
            f"{msgs_block}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.agnes_request_timeout)
            ) as client:
                response = await client.post(
                    f"{settings.agnes_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.agnes_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.agnes_model,
                        "messages": [
                            {"role": "system", "content": AgnesService.BATCH_PROMPT},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.0,
                        "max_tokens": 2048,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

        except Exception as exc:
            logger.error("Agnes batch extraction failed: %s", exc, exc_info=True)
            return None

        return AgnesService._parse_batch_json(content)

    @staticmethod
    async def classify_and_extract(
        text: str,
        msg_created_at: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Single-pass classification + multi-event extraction via Agnes 2.0 Flash.

        Args:
            text: The incoming WhatsApp message raw text
            msg_created_at: Optional anchor timestamp for relative date parsing

        Returns:
            Dict with classification + extraction fields & events array, or None on failure.
        """
        anchor_str = AgnesService._format_anchor_timestamp(msg_created_at)

        user_content = (
            f"Reference Timestamp Anchor: {anchor_str}\n\n"
            f"Message:\n{text}"
        )

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.agnes_request_timeout)
            ) as client:
                response = await client.post(
                    f"{settings.agnes_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.agnes_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.agnes_model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "temperature": 0.0,
                        "max_tokens": 1024,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

        except Exception as exc:
            logger.error("Agnes classification+extraction failed: %s", exc, exc_info=True)
            return None

        return AgnesService._parse_json_response(content, fallback_text=text)

    @staticmethod
    def _parse_json_response(raw: str, fallback_text: str = "") -> Optional[Dict[str, Any]]:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        try:
            parsed = SingleMessageAIResponse.model_validate_json(raw)
        except Exception as exc:
            logger.warning("Agnes single output validation failed (%s), attempting raw dict parse: %s", exc, raw[:300])
            try:
                raw_dict = json.loads(raw)
                parsed = SingleMessageAIResponse.model_validate(raw_dict)
            except Exception:
                logger.error("Agnes returned invalid JSON payload: %s", raw[:500])
                return None

        classification = parsed.classification.upper()
        if classification not in ("SIGNAL", "NOISE"):
            classification = "NOISE"

        processed_events = []
        for ev in parsed.events:
            ev_dict = ev.model_dump()
            cat = (ev_dict.get("category") or "INFO").upper()
            if cat not in ("DEADLINE", "EVENT", "ALERT", "INFO"):
                cat = "INFO"
            ev_dict["category"] = cat
            ev_dict["title"] = _trunc_title(ev_dict.get("title") or "Academic Update", 80)
            if not ev_dict.get("description"):
                ev_dict["description"] = fallback_text or ev_dict["title"]
            processed_events.append(ev_dict)

        primary_event = processed_events[0] if processed_events else {}

        res = {
            "classification": classification,
            "action_type": primary_event.get("action_type", "CREATE"),
            "category": primary_event.get("category", "INFO"),
            "course_code": primary_event.get("course_code"),
            "title": primary_event.get("title", "Academic Update"),
            "description": primary_event.get("description", fallback_text or "Academic Update"),
            "venue": primary_event.get("venue"),
            "date_time": primary_event.get("date_time"),
            "lecturer": primary_event.get("lecturer"),
            "urgency_score": primary_event.get("urgency_score", 0.5),
            "confidence_score": primary_event.get("confidence_score", 0.8),
            "relevance_score": primary_event.get("relevance_score", 0.7),
            "actionability_score": primary_event.get("actionability_score", 0.6),
            "needs_review": primary_event.get("needs_review", False),
            "event_completeness": primary_event.get("event_completeness", "complete"),
            "events": processed_events,
        }
        return res

    @staticmethod
    def _parse_batch_json(raw: str) -> Optional[List[Dict[str, Any]]]:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        try:
            parsed_batch = BatchMessageAIResponse.model_validate_json(raw)
            items = parsed_batch.items
        except Exception:
            try:
                raw_dict = json.loads(raw)
                if isinstance(raw_dict, list):
                    raw_dict = {"items": raw_dict}
                parsed_batch = BatchMessageAIResponse.model_validate(raw_dict)
                items = parsed_batch.items
            except Exception as exc:
                logger.error("Agnes batch returned invalid JSON (%s): %s", exc, raw[:500])
                return None

        results = []
        for item in items:
            classification = item.classification.upper()
            if classification not in ("SIGNAL", "NOISE"):
                classification = "NOISE"

            processed_events = []
            for ev in item.events:
                ev_dict = ev.model_dump()
                cat = (ev_dict.get("category") or "INFO").upper()
                if cat not in ("DEADLINE", "EVENT", "ALERT", "INFO"):
                    cat = "INFO"
                ev_dict["category"] = cat
                ev_dict["title"] = _trunc_title(ev_dict.get("title") or "Academic Update", 80)
                processed_events.append(ev_dict)

            primary_event = processed_events[0] if processed_events else {}

            item_res = {
                "index": item.index,
                "classification": classification,
                "action_type": primary_event.get("action_type", "CREATE"),
                "category": primary_event.get("category", "INFO"),
                "course_code": primary_event.get("course_code"),
                "title": primary_event.get("title", "Academic Update"),
                "description": primary_event.get("description", "Academic Update"),
                "venue": primary_event.get("venue"),
                "date_time": primary_event.get("date_time"),
                "lecturer": primary_event.get("lecturer"),
                "urgency_score": primary_event.get("urgency_score", 0.5),
                "confidence_score": primary_event.get("confidence_score", 0.8),
                "relevance_score": primary_event.get("relevance_score", 0.7),
                "actionability_score": primary_event.get("actionability_score", 0.6),
                "needs_review": primary_event.get("needs_review", False),
                "event_completeness": primary_event.get("event_completeness", "complete"),
                "events": processed_events,
            }
            results.append(item_res)

        return results


def _trunc_title(title: str, max_len: int = 80) -> str:
    if not title:
        return "Academic Update"
    if len(title) <= max_len:
        return title
    return title[:(max_len - 3)] + "..."