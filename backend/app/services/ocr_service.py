"""
OCR Extraction Service
Uses pytesseract + OpenCV for image text extraction and event parsing.
PaddleOCR can be substituted by swapping _extract_text().
"""
import io
import re
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Optional library imports ───────────────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    logger.warning("pytesseract/Pillow not installed — OCR will not work. Run: pip install pytesseract Pillow")

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("opencv-python-headless not installed — image preprocessing disabled")

# Lazy-init PaddleOCR so the (multi-second) model load only happens on the
# first OCR request — not on every worker boot / test import.
_paddle = None
_paddle_lock = threading.Lock()
HAS_PADDLE_IMPORT = False
_paddle_import_error: Optional[BaseException] = None
try:
    import paddleocr  # noqa: F401 — checked by HAS_PADDLE_IMPORT
    HAS_PADDLE_IMPORT = True
except ImportError:
    logger.warning("paddleocr not installed — falling back to pytesseract when available")


def _get_paddle():
    global _paddle
    if _paddle is not None:
        return _paddle
    with _paddle_lock:
        if _paddle is not None:
            return _paddle
        try:
            import paddleocr as _po
            _paddle = _po.PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            return _paddle
        except Exception as exc:
            logger.error("PaddleOCR init failed: %s", exc)
            return None


def _paddle_available() -> bool:
    return HAS_PADDLE_IMPORT and _get_paddle() is not None


HAS_PADDLE = HAS_PADDLE_IMPORT  # legacy alias used by /status endpoint


class OCRService:
    """Service for extracting academic events from images"""

    # ── Public entry point ────────────────────────────────────────────────────

    @staticmethod
    def process_image(image_bytes: bytes, user_instructions: Optional[str] = None) -> Dict[str, Any]:
        """
        Full pipeline: preprocess → extract text → parse events → apply filters.
        Returns a dict with keys: raw_text, structured_events, applied_filters.
        """
        # Step 1: Extract raw text
        raw_text = OCRService._extract_text(image_bytes)
        if not raw_text or not raw_text.strip():
            return {
                "raw_text": "",
                "structured_events": [],
                "applied_filters": user_instructions,
            }

        # Step 2: Parse into structured academic events
        events = OCRService._parse_events(raw_text)

        # Step 3: Apply natural-language instruction filters
        if user_instructions and events:
            events = OCRService._apply_filters(events, user_instructions)

        return {
            "raw_text": raw_text,
            "structured_events": events,
            "applied_filters": user_instructions,
        }

    # ── Text extraction ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_text(image_bytes: bytes) -> str:
        """Extract text from raw image bytes using PaddleOCR (preferred) or pytesseract"""
        # Preprocess image first
        processed = OCRService._preprocess_image(image_bytes)

        # Try PaddleOCR first (higher accuracy)
        paddle = _get_paddle()
        if paddle is not None:
            try:
                result = paddle.ocr(processed, cls=True)
                lines = []
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) > 1:
                            lines.append(line[1][0])
                return "\n".join(lines)
            except Exception as e:
                logger.error(f"PaddleOCR failed: {e}")

        # Fallback: pytesseract
        if HAS_TESSERACT:
            try:
                img = Image.open(io.BytesIO(processed if isinstance(processed, bytes) else image_bytes))
                return pytesseract.image_to_string(img, config="--psm 6")
            except Exception as e:
                logger.error(f"pytesseract failed: {e}")

        logger.error("No OCR engine available")
        return ""

    @staticmethod
    def _preprocess_image(image_bytes: bytes) -> bytes:
        """
        Preprocess image with OpenCV for better OCR accuracy:
        - Resize to reasonable dimensions
        - Convert to grayscale
        - Apply contrast enhancement (CLAHE)
        - Denoise
        """
        if not HAS_CV2:
            return image_bytes

        try:
            arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

            if img is None:
                return image_bytes

            # Resize if too small
            h, w = img.shape[:2]
            if w < 800:
                scale = 800 / w
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

            # Grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # CLAHE contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

            # Encode back to bytes
            success, buffer = cv2.imencode(".png", denoised)
            if success:
                return buffer.tobytes()

        except Exception as e:
            logger.error(f"Image preprocessing error: {e}")

        return image_bytes

    # ── Event parsing ─────────────────────────────────────────────────────────

    # Course code pattern: 3 letters + optional space + 3 digits (e.g. ELE310, CSC 401)
    COURSE_CODE_RE = re.compile(r"\b([A-Z]{3})\s?(\d{3})\b")

    # Date patterns
    DATE_PATTERNS = [
        re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"),                  # 12/06/2024
        re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
                   r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
                   r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:,?\s*(\d{4}))?\b",
                   re.IGNORECASE),
    ]

    # Time pattern: 10:00 AM, 10am, 14:30
    TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)

    # Venue hints
    VENUE_RE = re.compile(r"\b(?:hall|room|auditorium|lab|theatre|theater|venue|llt|blt|elt)\s*[A-Z0-9]*\b",
                           re.IGNORECASE)

    # Event type keyword map
    EVENT_KEYWORDS = {
        "DEADLINE": ["assignment", "submit", "submission", "due", "project", "coursework"],
        "ALERT": ["cancel", "cancelled", "postponed", "moved", "rescheduled", "urgent", "alert"],
        "EVENT": ["seminar", "workshop", "meeting", "orientation", "lecture", "guest", "program"],
        "EXAM": ["exam", "test", "quiz", "ca", "continuous assessment", "gce"],
    }

    @staticmethod
    def _parse_events(text: str) -> List[Dict[str, Any]]:
        """
        Parse raw OCR text into a list of structured academic event dicts.
        Each dict has: course_code, event_type, title, date_str, time_str, venue, raw_line
        """
        events = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for line in lines:
            # Must contain a course code to be considered academic
            course_match = OCRService.COURSE_CODE_RE.search(line)
            if not course_match:
                continue

            course_code = f"{course_match.group(1)}{course_match.group(2)}"

            # Determine event type
            event_type = "INFO"
            line_lower = line.lower()
            for et, keywords in OCRService.EVENT_KEYWORDS.items():
                if any(kw in line_lower for kw in keywords):
                    event_type = "DEADLINE" if et == "EXAM" else et
                    break

            # Extract date
            date_str = None
            for pat in OCRService.DATE_PATTERNS:
                m = pat.search(line)
                if m:
                    date_str = m.group(0)
                    break

            # Extract time
            time_str = None
            tm = OCRService.TIME_RE.search(line)
            if tm:
                time_str = tm.group(0)

            # Extract venue
            venue = None
            vm = OCRService.VENUE_RE.search(line)
            if vm:
                venue = vm.group(0).strip()

            events.append({
                "course_code": course_code,
                "event_type": event_type,
                "title": line[:200],
                "date_str": date_str,
                "time_str": time_str,
                "venue": venue,
                "raw_line": line,
            })

        return events

    # ── Instruction filter ────────────────────────────────────────────────────

    @staticmethod
    def _apply_filters(events: List[Dict], instructions: str) -> List[Dict]:
        """
        Apply natural-language instruction filters to extracted events.
        Supported: level filters (100/200/300-level), department (ELE/CSC),
                   date hints (this week / tomorrow), exclusions (ignore GST).
        """
        inst_lower = instructions.lower()

        # Department filter: "only ELE courses", "save CSC"
        dept_include = re.findall(r"\b([A-Z]{3})\b", instructions.upper())

        # Level filter: "only 300-level", "200 level courses"
        level_match = re.search(r"\b(100|200|300|400|500)-?\s*level\b", inst_lower)
        target_level = level_match.group(1) if level_match else None

        # Exclusion filter: "ignore GST", "exclude practicals"
        ignore_dept = re.findall(r"(?:ignore|exclude)\s+([A-Z]{3})\b", instructions.upper())

        # Date filter
        filter_tomorrow = "tomorrow" in inst_lower
        filter_this_week = "this week" in inst_lower

        filtered = []
        for ev in events:
            cc = ev.get("course_code", "")
            dept = cc[:3] if len(cc) >= 3 else ""
            level = cc[3] + "00" if len(cc) >= 4 else None

            # Apply exclusions
            if ignore_dept and dept in ignore_dept:
                continue

            # Apply department include filter
            if dept_include and dept not in dept_include:
                continue

            # Apply level filter
            if target_level and level and level != target_level:
                continue

            # Date filters (simplified — check presence of "tomorrow" or current week dates)
            if filter_tomorrow and ev.get("date_str"):
                tomorrow_str = (datetime.utcnow() + timedelta(days=1)).strftime("%d")
                if tomorrow_str not in ev["date_str"]:
                    continue

            filtered.append(ev)

        return filtered
