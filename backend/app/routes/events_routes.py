"""
API Routes - Academic Events Management
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import AcademicEvent, User
from app.schemas import AcademicEventResponse, AcademicEventCreate, AcademicEventListResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["Academic Events"])


def get_current_user(
    authorization: str = Header(None),
    token: str = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user"""
    actual_token = token
    if authorization and authorization.startswith("Bearer "):
        actual_token = authorization.split(" ")[1]

    if not actual_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token provided",
        )
    user = AuthService.get_user_from_token(actual_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user


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
    List academic events for current user
    """
    try:
        query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
        )

        # Apply filters
        if event_type:
            query = query.filter(AcademicEvent.event_type == event_type)

        if course_code:
            query = query.filter(AcademicEvent.course_code == course_code)

        # Get total count
        total = query.count()

        # Get paginated results
        events = query.order_by(
            AcademicEvent.date_time.desc()
        ).offset(skip).limit(limit).all()

        return {
            "items": events,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list events",
        )


@router.get("/{event_id}", response_model=AcademicEventResponse)
async def get_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific academic event
    """
    try:
        event = db.query(AcademicEvent).filter(
            AcademicEvent.id == event_id,
            AcademicEvent.user_id == user.id,
        ).first()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )

        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get event",
        )


@router.post("", response_model=AcademicEventResponse)
async def create_event(
    event_data: AcademicEventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new academic event (manual entry)
    """
    try:
        # Create event
        event = AcademicEvent(
            user_id=user.id,
            group_id=None,  # Manual entry
            event_type=event_data.event_type,
            course_code=event_data.course_code,
            title=event_data.title,
            description=event_data.description,
            venue=event_data.venue,
            date_time=event_data.date_time,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        logger.info(f"Event created: {event.id}")
        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event",
        )


@router.delete("/{event_id}")
async def delete_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Archive an academic event
    """
    try:
        event = db.query(AcademicEvent).filter(
            AcademicEvent.id == event_id,
            AcademicEvent.user_id == user.id,
        ).first()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )

        event.is_archived = True
        db.commit()

        logger.info(f"Event archived: {event_id}")
        return {"message": "Event archived successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete event",
        )
