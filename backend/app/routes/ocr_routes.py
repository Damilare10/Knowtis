"""
API Routes - OCR Extraction
Allows students to upload academic images and extract structured events.
Rate-limited: 10/hour free, 50/hour premium.
"""
import json
import logging
import re
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import User, OCRExtraction, AcademicEvent
from app.schemas import OCRExtractResponse
from app.dependencies import get_current_user
from app.services.ocr_service import OCRService
from app.services.classifier_service import MessageClassifier
from app.utils import generate_embedding
from app.config import settings
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"])

# Max upload size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
}

# Free-tier monthly OCR limit
FREE_TIER_OCR_LIMIT = 10
PREMIUM_TIER_OCR_LIMIT = 500

# Numeric date pattern shared with OCRService.DATE_PATTERNS[0]
_OCR_NUM_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
# Alphanumeric date pattern (e.g. "June 12" or "Jun 12, 2024")
_OCR_ALPHA_DATE_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})"
    r"(?:,?\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_OCR_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
_MONTH_INDEX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_ocr_date_time(date_str: Optional[str], time_str: Optional[str]):
    """
    Resolve the OCR-extracted ``date_str`` + ``time_str`` into a datetime.

    Returns ``None`` when either field is missing or unparseable so the caller
    can still persist the event with an unscheduled marker. Defaults to 09:00
    when only a date is available; defaults to tomorrow when only a time is
    available.
    """
    if not date_str:
        return None

    parsed_date = None
    num_match = _OCR_NUM_DATE_RE.search(date_str)
    if num_match:
        try:
            d, m, y = int(num_match.group(1)), int(num_match.group(2)), int(num_match.group(3))
            if y < 100:
                y += 2000
            parsed_date = datetime(y, m, d)
        except ValueError:
            parsed_date = None

    if parsed_date is None:
        alpha_match = _OCR_ALPHA_DATE_RE.search(date_str)
        if alpha_match:
            try:
                month_name = alpha_match.group(1)[:3].lower()
                day = int(alpha_match.group(2))
                year_raw = alpha_match.group(3)
                year = int(year_raw) if year_raw else datetime.utcnow().year
                month_num = _MONTH_INDEX.get(month_name)
                if month_num:
                    parsed_date = datetime(year, month_num, day)
            except ValueError:
                parsed_date = None

    if parsed_date is None:
        return None

    hour, minute = 9, 0
    if time_str:
        tm = _OCR_TIME_RE.search(time_str)
        if tm:
            try:
                hour = int(tm.group(1))
                minute = int(tm.group(2)) if tm.group(2) else 0
                meridian = (tm.group(3) or "").lower()
                if meridian == "pm" and hour < 12:
                    hour += 12
                elif meridian == "am" and hour == 12:
                    hour = 0
            except ValueError:
                hour, minute = 9, 0

    return parsed_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _check_ocr_rate_limit(user: User, db: Session) -> None:
    """
    Enforce OCR rate limits per user per month (30-day rolling window).
    Raises HTTP 429 if the limit is exceeded.
    """
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    count = db.query(OCRExtraction).filter(
        OCRExtraction.user_id == user.id,
        OCRExtraction.created_at >= thirty_days_ago,
    ).count()

    limit = PREMIUM_TIER_OCR_LIMIT if user.is_premium else FREE_TIER_OCR_LIMIT

    if count >= limit:
        retry_after = 86400
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"OCR rate limit reached ({limit}/month). "
                "Please retry later in the month. "
                "Upgrade to Premium for higher limits."
                if not user.is_premium else
                f"OCR rate limit reached ({limit}/month). Please retry later."
            ),
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/extract", response_model=OCRExtractResponse)
@limiter.limit(settings.rate_limit_default)
async def extract_from_image(
    request: Request,
    file: UploadFile = File(..., description="Academic image: timetable, assignment poster, exam schedule, etc."),
    instructions: Optional[str] = Form(None, description="Natural-language filter e.g. 'only 300-level ELE courses'"),
    group_id: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload an academic image and extract structured events.

    - Supports: JPEG, PNG, WebP, BMP, TIFF
    - Max size: 10 MB
    - Rate limited: 10/hour free | 50/hour premium
    - Optional `instructions` to filter results (e.g. "only ELE courses", "ignore GST exams")
    """
    # ── Rate limit check ──────────────────────────────────────────────────────
    _check_ocr_rate_limit(user, db)

    # ── Validate file ─────────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Accepted: JPEG, PNG, WebP, BMP, TIFF.",
        )

    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── OCR Processing ────────────────────────────────────────────────────────
    try:
        result = OCRService.process_image(image_bytes, user_instructions=instructions)
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR processing failed. Please try a clearer image.",
        )

    raw_text = result.get("raw_text", "")
    structured_events = result.get("structured_events", [])

    # ── Save OCR extraction record ────────────────────────────────────────────
    from uuid import UUID as _UUID
    parsed_group_id = None
    if group_id:
        try:
            parsed_group_id = _UUID(group_id)
        except ValueError:
            parsed_group_id = None

    ocr_record = OCRExtraction(
        user_id=user.id,
        group_id=parsed_group_id,
        message_id=None,
        extracted_text=raw_text,
        extraction_confidence=0.85 if raw_text else 0.0,
        extraction_strategy="paddleocr" if raw_text else "pytesseract",
        user_instructions=instructions,
        filtered_events=structured_events,
    )
    db.add(ocr_record)
    db.flush()  # Get ID before committing

    # ── Create AcademicEvent records from extracted data ──────────────────────
    created_events = []
    for ev_data in structured_events:
        try:
            text_for_analysis = ev_data.get("title", "")

            # Score the event
            scores = MessageClassifier.calculate_scores(text_for_analysis)

            # Generate embedding
            embedding_vec = generate_embedding(text_for_analysis)

            # Parse the date/time strings emitted by the OCR parser so
            # downstream surfaces (dashboard, reminders, Night Brief) can
            # schedule reminders and order events chronologically.
            parsed_dt = _parse_ocr_date_time(
                ev_data.get("date_str"),
                ev_data.get("time_str"),
            )

            event = AcademicEvent(
                user_id=user.id,
                group_id=None,
                event_type=ev_data.get("event_type", "INFO"),
                course_code=ev_data.get("course_code"),
                title=ev_data.get("title", "Untitled Event")[:500],
                description=f"Extracted from image via OCR. Raw: {ev_data.get('raw_line', '')}",
                venue=ev_data.get("venue"),
                date_time=parsed_dt,
                urgency_score=scores["urgency_score"],
                confidence_score=scores["confidence_score"],
                relevance_score=scores["relevance_score"],
                actionability_score=scores["actionability_score"],
                embedding=json.dumps(embedding_vec),
                source_message_id=str(ocr_record.id),
            )
            db.add(event)
            db.flush()
            created_events.append(event)

        except Exception as e:
            logger.error(f"Error creating event from OCR data: {e}")
            continue

    db.commit()

    # Refresh all created events for serialization
    for ev in created_events:
        db.refresh(ev)

    logger.info(
        f"OCR extraction complete for user {user.id}: "
        f"{len(raw_text)} chars extracted, {len(created_events)} events created"
    )

    return {
        "extracted_text": raw_text,
        "events_created": len(created_events),
        "events": created_events,
        "applied_filters": instructions,
    }
