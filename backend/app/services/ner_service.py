"""
Named Entity Recognition (NER) Service
Extracts academic entities (COURSE_CODE, LECTURER, LOCATION, DATE, TIME) from messages.
Integrates GLiNER (when available) with an LLM and Database-backed Student Knowledge Base fallback.
"""
import re
import json
import logging
import asyncio
from typing import Dict, Optional, Any

from sqlalchemy.orm import Session
from app.services.llm_service import LLMService
from app.models import StudentKnowledgeBase

logger = logging.getLogger(__name__)

# Try to import GLiNER, but keep the regex/LLM path healthy when optional ML
# dependencies are not installed on a local machine.
try:
    from gliner import GLiNER
except Exception as exc:
    GLiNER = None
    logger.info("GLiNER is unavailable; NER will use regex/LLM fallback: %s", exc)

# Lazy-load to avoid slowing down import times.
_gliner_model = None

try:
    import torch
except Exception:
    torch = None

if torch is not None:
    try:
        torch.classes.__path__ = []
    except Exception:
        pass

if GLiNER is None:
    _gliner_model = None


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


class NERService:
    """Service to extract named entities using local ML, regex, and LLM fallbacks."""

    @staticmethod
    def _get_gliner():
        global _gliner_model
        if GLiNER is None:
            return None
        if _gliner_model is None:
            try:
                # Load a small lightweight gliner model
                _gliner_model = GLiNER.from_pretrained("urchade/gliner_small")
            except Exception as e:
                logger.warning("Failed to initialize GLiNER model: %s", e)
                _gliner_model = False  # Mark as failed to avoid retrying
        return _gliner_model if _gliner_model is not False else None

    @staticmethod
    def extract_entities(text: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Main entrypoint. Extracts course_code, lecturer, location, date, time.
        Synchronous wrapper around the async implementation.
        """
        return _run_async(NERService.extract_entities_async(text, db))

    @staticmethod
    async def extract_entities_async(text: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Asynchronously extracts entities, running local GLiNER first, falling back to LLM.
        Applies StudentKnowledgeBase dictionary mappings afterwards.
        """
        if not text or not text.strip():
            return {
                "course_code": None,
                "lecturer": None,
                "location": None,
                "date": None,
                "time": None
            }

        entities = None
        course_match = re.search(r"\b([A-Za-z]{3})\s?(\d{3})\b", text)
        regex_course_code = f"{course_match.group(1).upper()}{course_match.group(2)}" if course_match else None

        # 1. Try local GLiNER if imported and available
        gliner_model = NERService._get_gliner()
        if gliner_model:
            try:
                labels = ["course code", "lecturer", "location", "date", "time"]
                # predict entities
                predictions = gliner_model.predict_entities(text, labels, threshold=0.4)
                
                entities = {
                    "course_code": None,
                    "lecturer": None,
                    "location": None,
                    "date": None,
                    "time": None
                }
                # Map GLiNER output to our schema (picking the highest score for each label)
                pred_by_label = {}
                for pred in predictions:
                    lbl = pred["label"].replace(" ", "_")
                    if lbl not in pred_by_label or pred["score"] > pred_by_label[lbl]["score"]:
                        pred_by_label[lbl] = pred

                for lbl, pred in pred_by_label.items():
                    entities[lbl] = pred["text"]

            except Exception as e:
                logger.warning("GLiNER prediction failed, falling back: %s", e)

        # 2. Fall back to LLM if GLiNER is missing or failed
        if not entities and LLMService.is_available():
            try:
                system_prompt = (
                    "You are a Named Entity Recognition (NER) system specialized in university student groups. "
                    "Extract the following entities from the message:\n"
                    "- COURSE_CODE: Course codes (e.g. CSC 301, MCE 402, GNS 201, or null)\n"
                    "- LECTURER: Name of lecturer (e.g. Dr. Taiwo, Prof. Adebayo, or null)\n"
                    "- LOCATION: Classroom or hall (e.g. LT1, LLT, CSC Lab, Auditorium, or null)\n"
                    "- DATE: Date mention (e.g. Friday, tomorrow, next Monday, 12/06, or null)\n"
                    "- TIME: Time mention (e.g. 10:00 AM, 2pm, by 4:00pm, or null)\n\n"
                    "Return ONLY a raw JSON object with keys: 'COURSE_CODE', 'LECTURER', 'LOCATION', 'DATE', 'TIME'. "
                    "Do not include markdown blocks, backticks, or extra commentary."
                )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Text: {text}"}
                ]

                response_str = await LLMService.chat(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=150
                )

                clean_response = response_str.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                parsed = json.loads(clean_response)
                entities = {
                    "course_code": parsed.get("COURSE_CODE"),
                    "lecturer": parsed.get("LECTURER"),
                    "location": parsed.get("LOCATION"),
                    "date": parsed.get("DATE"),
                    "time": parsed.get("TIME")
                }
            except Exception as e:
                logger.warning("NER LLM extraction failed: %s", e)

        # 3. Simple Regex heuristic fallback (if LLM and GLiNER both failed)
        if not entities:
            course_match = re.search(r"\b([A-Za-z]{3})\s?(\d{3})\b", text)
            course_code = f"{course_match.group(1).upper()}{course_match.group(2)}" if course_match else None
            
            lect_match = re.search(r"\b(Dr\.|Prof\.|Mr\.|Mrs\.|Engr\.)\s*([A-Z][a-z]+)\b", text)
            lecturer = lect_match.group(0) if lect_match else None

            venue_re = re.compile(
                r"\b(?:hall|room|auditorium|lab|theatre|theater|venue|llt|blt|elt)\s*[A-Z0-9]*\b",
                re.IGNORECASE
            )
            venue_match = venue_re.search(text)
            location = venue_match.group(0) if venue_match else None

            entities = {
                "course_code": course_code,
                "lecturer": lecturer,
                "location": location,
                "date": None,
                "time": None
            }

        if regex_course_code:
            entities["course_code"] = regex_course_code

        # 4. Resolve Course Codes and Lecturers using StudentKnowledgeBase
        if db and entities.get("course_code"):
            norm_code = re.sub(r"\s+", "", entities["course_code"]).upper()
            # Clean up course code structure (e.g. CSC301)
            course_match = re.match(r"^([A-Z]{3})(\d{3})$", norm_code)
            if course_match:
                clean_code = f"{course_match.group(1)}{course_match.group(2)}"
                
                # Check DB for full name mappings or abbreviation lookups
                kb_entry = db.query(StudentKnowledgeBase).filter(
                    StudentKnowledgeBase.course_code == clean_code
                ).first()
                if kb_entry:
                    entities["course_title"] = kb_entry.full_name
                    if not entities["lecturer"] and kb_entry.lecturer_name:
                        entities["lecturer"] = kb_entry.lecturer_name
                entities["course_code"] = clean_code
            else:
                entities["course_code"] = norm_code

        # If no course code, try to find abbreviation in KB
        if db and not entities.get("course_code"):
            # Check if any database course code full name or abbreviations are in the text
            kb_entries = db.query(StudentKnowledgeBase).all()
            text_lower = text.lower()
            for entry in kb_entries:
                # Check abbreviation synonyms
                abbrevs = entry.abbreviations or []
                match_found = False
                for abbrev in abbrevs:
                    if re.search(rf"\b{re.escape(abbrev.lower())}\b", text_lower):
                        match_found = True
                        break
                
                if match_found or entry.course_code.lower() in text_lower:
                    entities["course_code"] = entry.course_code
                    entities["course_title"] = entry.full_name
                    if not entities["lecturer"] and entry.lecturer_name:
                        entities["lecturer"] = entry.lecturer_name
                    break

        return entities
