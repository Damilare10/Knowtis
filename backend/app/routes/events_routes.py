"""
API Routes - Academic Events Management
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from uuid import UUID
from app.database import get_db
from app.models import AcademicEvent, User, EventType, EventStatus, WhatsAppGroup
from app.schemas import (
    AcademicEventResponse, AcademicEventCreate, AcademicEventUpdate,
    AcademicEventListResponse, SemanticSearchResponse
)
from app.dependencies import get_current_user
from app.services.deduplication_service import DeduplicationService
from app.services.search_service import SearchService
from app.services.reminder_service import ReminderService
from app.services.urgency_service import compute_urgency
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
    List academic events for the authenticated user with source group provenance.
    Filters out superseded events and signals tier-based truncation.
    """
    try:
        query = (
            db.query(AcademicEvent, WhatsAppGroup.group_name)
            .outerjoin(WhatsAppGroup, AcademicEvent.group_id == WhatsAppGroup.id)
            .filter(
                AcademicEvent.user_id == user.id,
                AcademicEvent.is_archived == False,
                AcademicEvent.is_duplicate == False,
                AcademicEvent.status != EventStatus.SUPERSEDED,
            )
        )

        if event_type:
            query = query.filter(AcademicEvent.event_type == event_type)
        if course_code:
            query = query.filter(func.lower(
                AcademicEvent.course_code) == course_code.lower())

        total = query.count()

        # Order by urgency (descending), then by date
        ordered = query.order_by(
            AcademicEvent.urgency_score.desc(),
            AcademicEvent.date_time.asc(),
        )

        truncated = False
        plan_limit = None
        if not user.is_premium:
            rows = ordered.limit(FREE_TIER_LIMIT).all()
            if total > FREE_TIER_LIMIT:
                truncated = True
                plan_limit = FREE_TIER_LIMIT
        else:
            rows = ordered.offset(skip).limit(limit).all()

        items = []
        for event, grp_name in rows:
            if grp_name:
                setattr(event, "group_name", grp_name)
            items.append(event)

        return {
            "items": items,
            "total": total,
            "skip": skip if user.is_premium else 0,
            "limit": limit,
            "truncated": truncated,
            "plan_limit": plan_limit,
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

        results = []
        for event, similarity in matches:
            if event.group:
                setattr(event, "group_name", event.group.group_name)
            results.append({"event": event, "similarity": similarity})

        return results

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
    """Get a specific academic event by ID including provenance"""
    try:
        row = (
            db.query(AcademicEvent, WhatsAppGroup.group_name)
            .outerjoin(WhatsAppGroup, AcademicEvent.group_id == WhatsAppGroup.id)
            .filter(
                AcademicEvent.id == event_id,
                AcademicEvent.user_id == user.id,
            )
            .first()
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found.",
            )

        event, grp_name = row
        if grp_name:
            setattr(event, "group_name", grp_name)
        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get event.",
        )

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
            logger.info(
                f"Duplicate detected — linking to canonical event {canonical_id}")

        # ── Persist event ─────────────────────────────────────────────────────
        # The user supplied these fields directly, so there is no model
        # prediction to score: confidence/relevance/actionability are 1.0 by
        # definition. Urgency is still DERIVED from the deadline rather than
        # guessed from keywords in the title.
        event = AcademicEvent(
            user_id=user.id,
            group_id=None,
            event_type=event_data.event_type,
            course_code=event_data.course_code,
            title=event_data.title,
            description=event_data.description,
            venue=event_data.venue,
            date_time=event_data.date_time,
            confidence_score=1.0,
            relevance_score=1.0,
            actionability_score=1.0,
            embedding=embedding_str,
            is_duplicate=is_duplicate,
            canonical_event_id=canonical_id,
        )
        event.urgency_score = compute_urgency(event)

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


@router.put("/{event_id}", response_model=AcademicEventResponse)
async def update_event(
    event_id: UUID,
    payload: AcademicEventUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an academic event's core details, mark review complete, record revision history,
    and recompute urgency.
    """
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

        changes = {}
        if payload.title is not None and payload.title != event.title:
            changes["title"] = {"old": event.title, "new": payload.title}
            event.title = payload.title
        if payload.course_code is not None and payload.course_code != event.course_code:
            changes["course_code"] = {"old": event.course_code, "new": payload.course_code}
            event.course_code = payload.course_code
        if payload.date_time is not None and payload.date_time != event.date_time:
            changes["date_time"] = {"old": str(event.date_time), "new": str(payload.date_time)}
            event.date_time = payload.date_time
        if payload.venue is not None and payload.venue != event.venue:
            changes["venue"] = {"old": event.venue, "new": payload.venue}
            event.venue = payload.venue
        if payload.event_type is not None and payload.event_type != event.event_type:
            changes["event_type"] = {"old": str(event.event_type), "new": str(payload.event_type)}
            event.event_type = payload.event_type

        event.needs_review = False
        rev = list(event.revisions or [])
        rev.append({
            "action": "USER_UPDATE",
            "timestamp": datetime.utcnow().isoformat(),
            "changes": changes,
        })
        event.revisions = rev
        event.urgency_score = compute_urgency(event)
        event.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(event)

        if event.group:
            setattr(event, "group_name", event.group.group_name)

        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating event {event_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update event.",
        )

