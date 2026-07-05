"""
API Routes - Academic Events Management
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import AcademicEvent, User, EventType
from app.schemas import AcademicEventResponse, AcademicEventCreate, AcademicEventListResponse, SemanticSearchResponse
from app.dependencies import get_current_user
from app.services.classifier_service import MessageClassifier
from app.services.deduplication_service import DeduplicationService
from app.services.search_service import SearchService
from app.services.reminder_service import ReminderService
from app.utils import generate_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["Academic Events"])

# Free-tier cascade display limit (PRD §9 — "Top 3 events")
FREE_TIER_LIMIT = 3
PREMIUM_TIER_LIMIT = 100  # Effectively unlimited with pagination


@router.get("", response_model=AcademicEventListResponse)
async def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    event_type: str = Query(None),
    course_code: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List academic events for the authenticated user.
    Free-tier users see a maximum of 3 events, ordered by urgency.
    Premium users get full paginated access.
    """
    try:
        query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            AcademicEvent.is_duplicate == False,
        )

        if event_type:
            query = query.filter(AcademicEvent.event_type == event_type)
        if course_code:
            query = query.filter(AcademicEvent.course_code == course_code)

        total = query.count()

        # Order by urgency (descending), then by date
        ordered = query.order_by(
            AcademicEvent.urgency_score.desc(),
            AcademicEvent.date_time.asc(),
        )

        # Enforce tier limits
        if not user.is_premium:
            events = ordered.limit(FREE_TIER_LIMIT).all()
            effective_total = min(total, FREE_TIER_LIMIT)
        else:
            events = ordered.offset(skip).limit(limit).all()
            effective_total = total

        return {
            "items": events,
            "total": effective_total,
            "skip": skip if user.is_premium else 0,
            "limit": limit,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list events.",
        )


@router.get("/search", response_model=list[SemanticSearchResponse])
async def search_events(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    threshold: Optional[float] = Query(None, ge=0.0, le=1.0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search academic events semantically using vector similarity.
    Free tier limits query results to top 3 matches.
    Premium tier allows up to 20 matches.
    """
    try:
        # Tier limits mapping
        effective_limit = limit
        if not user.is_premium:
            effective_limit = min(limit, 3)
        else:
            effective_limit = min(limit, 20)

        matches = SearchService.search_events(
            user_id=user.id,
            query_text=query,
            db=db,
            limit=effective_limit,
            threshold=threshold
        )
        
        return [
            {"event": event, "similarity": similarity}
            for event, similarity in matches
        ]
        
    except Exception as e:
        logger.error(f"Error in semantic search endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic search failed.",
        )


@router.get("/{event_id}", response_model=AcademicEventResponse)
async def get_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific academic event by ID"""
    try:
        event = db.query(AcademicEvent).filter(
            AcademicEvent.id == event_id,
            AcademicEvent.user_id == user.id,
        ).first()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found.",
            )

        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get event.",
        )


@router.post("", response_model=AcademicEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: AcademicEventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually create an academic event.
    Runs NLP classification and deduplication automatically.
    """
    try:
        # Build a text representation for NLP and embedding
        text_for_analysis = f"{event_data.title} {event_data.description or ''} {event_data.course_code or ''}"

        # ── Score the event via classifier ────────────────────────────────────
        scores = MessageClassifier.calculate_scores(text_for_analysis)

        # ── Generate semantic embedding ───────────────────────────────────────
        embedding_vec = generate_embedding(text_for_analysis)
        embedding_str = json.dumps(embedding_vec)

        # ── Check for duplicates ──────────────────────────────────────────────
        canonical = DeduplicationService.find_duplicate(
            user_id=user.id,
            new_event_text=text_for_analysis,
            group_id=None,
            db=db,
        )

        is_duplicate = canonical is not None
        canonical_id = canonical.id if canonical else None

        if is_duplicate:
            logger.info(f"Duplicate detected — linking to canonical event {canonical_id}")

        # ── Persist event ─────────────────────────────────────────────────────
        event = AcademicEvent(
            user_id=user.id,
            group_id=None,
            event_type=event_data.event_type,
            course_code=event_data.course_code,
            title=event_data.title,
            description=event_data.description,
            venue=event_data.venue,
            date_time=event_data.date_time,
            urgency_score=scores["urgency_score"],
            confidence_score=scores["confidence_score"],
            relevance_score=scores["relevance_score"],
            actionability_score=scores["actionability_score"],
            embedding=embedding_str,
            is_duplicate=is_duplicate,
            canonical_event_id=canonical_id,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        if not event.is_duplicate and event.event_type != EventType.ALERT:
            # Only scheduled events/deadlines get reminder rows.
            ReminderService.schedule_automatic_reminders(event, db)

        logger.info(f"Event created: {event.id} (duplicate={is_duplicate})")
        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event.",
        )


@router.delete("/{event_id}")
async def delete_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-archive an academic event (sets is_archived=True)"""
    try:
        event = db.query(AcademicEvent).filter(
            AcademicEvent.id == event_id,
            AcademicEvent.user_id == user.id,
        ).first()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found.",
            )

        event.is_archived = True
        db.commit()

        logger.info(f"Event archived: {event_id}")
        return {"message": "Event archived successfully."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving event: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive event.",
        )
