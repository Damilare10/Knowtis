"""
Semantic Role Labeling (SRL) Service
Extracts {actor, action, object, time} from natural language student announcements.
"""
import re
import json
import logging
import asyncio
from typing import Dict, Optional, Any

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Run a coroutine from a synchronous context safely."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


class SRLService:
    """Service to identify key semantic roles (actor, action, object, time) in messages."""

    @staticmethod
    def extract_srl(text: str) -> Dict[str, Any]:
        """
        Extracts semantic roles from text.
        Synchronous wrapper around the async extractor.
        """
        return _run_async(SRLService.extract_srl_async(text))

    @staticmethod
    def extract_srl_regex(text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts quick rule-based regex extraction for very common announcement forms.
        Returns None if no clean match is found.
        """
        # Pattern 1: [Lecturer] moved/postponed [Course Code] [Test/Lecture] to [Time]
        # Example: "Dr. Taiwo moved the CSC 301 test to Thursday"
        pattern1 = re.compile(
            r"\b(Dr\.|Prof\.|Mr\.|Mrs\.|Engr\.)\s*([A-Z][a-z]+)\s+(moved|postponed|rescheduled)\s+(?:the\s+)?([A-Za-z]{3}\s?\d{3}\s+[\w\s]{3,20}?)\s+to\s+([\w\s,]+?)(?:\.|$)",
            re.IGNORECASE
        )
        match1 = pattern1.search(text)
        if match1:
            return {
                "actor": f"{match1.group(1)} {match1.group(2)}",
                "action": match1.group(3).lower(),
                "object": match1.group(4).strip(),
                "time": match1.group(5).strip()
            }

        # Pattern 2: [Course Code] [Lecture/Test] is cancelled/postponed
        # Example: "CSC 301 class is cancelled for today"
        pattern2 = re.compile(
            r"\b([A-Za-z]{3}\s?\d{3}\s+[\w\s]{3,20}?)\s+is\s+(cancelled|postponed|moved)\s+(?:for\s+)?([\w\s,]+?)(?:\.|$)",
            re.IGNORECASE
        )
        match2 = pattern2.search(text)
        if match2:
            return {
                "actor": None,
                "action": match2.group(2).lower(),
                "object": match2.group(1).strip(),
                "time": match2.group(3).strip()
            }

        return None

    @staticmethod
    async def extract_srl_async(text: str) -> Dict[str, Any]:
        """
        Asynchronously extracts SRL nodes. Falls back to regex if LLM is unavailable.
        """
        if not text or not text.strip():
            return {"actor": None, "action": None, "object": None, "time": None}

        # 1. Try regex first
        regex_result = SRLService.extract_srl_regex(text)
        if regex_result:
            logger.debug("SRL successfully extracted via regex: %s", regex_result)
            return regex_result

        # 2. Fall back to LLM if available
        if LLMService.is_available():
            try:
                system_prompt = (
                    "You are an NLP model performing Semantic Role Labeling (SRL) on student group announcements. "
                    "Extract the following roles:\n"
                    "- actor: the person/entity initiating the action (e.g., lecturer, department, representative, or null)\n"
                    "- action: the verb indicating the change or event (e.g., moved, cancelled, rescheduled, deadline, or null)\n"
                    "- object: the target course/activity being changed (e.g., CSC 301 test, homework, lecture, or null)\n"
                    "- time: when the event occurs or has been rescheduled to (e.g., Friday 2pm, tomorrow, or null)\n\n"
                    "Return ONLY a raw JSON object with keys: 'actor', 'action', 'object', 'time'. "
                    "Do not include markdown backticks or explanations."
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Message: {text}"}
                ]
                
                response_str = await LLMService.chat(
                    messages=messages,
                    temperature=0.0,  # Deterministic
                    max_tokens=150
                )
                
                # Clean potential markdown wrapping
                clean_response = response_str.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                parsed = json.loads(clean_response)
                return {
                    "actor": parsed.get("actor"),
                    "action": parsed.get("action"),
                    "object": parsed.get("object"),
                    "time": parsed.get("time")
                }
            except Exception as e:
                logger.warning("SRL LLM extraction failed: %s", e)

        # 3. Last resort: simple heuristic parse
        words = text.lower().split()
        time_hint = None
        for t_word in ["today", "tomorrow", "friday", "monday", "thursday", "wednesday", "tuesday", "saturday", "sunday"]:
            if t_word in words:
                time_hint = t_word
                break

        action_hint = None
        for a_word in ["cancel", "move", "postpone", "reschedule", "due", "submit"]:
            if any(a_word in w for w in words):
                action_hint = a_word
                break

        course_match = re.search(r"\b([A-Za-z]{3})\s?(\d{3})\b", text)
        object_hint = f"{course_match.group(0)} item" if course_match else "academic event"

        return {
            "actor": None,
            "action": action_hint,
            "object": object_hint,
            "time": time_hint
        }
