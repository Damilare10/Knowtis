"""
API Routes - Notifications
All routes query the real notification_inbox table.
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import NotificationInbox, AcademicEvent, EventType, User
from app.schemas import NotificationResponse, NightBriefResponse, AcademicEventResponse
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notification inbox for the current user"""
    try:
        query = db.query(NotificationInbox).filter(
            NotificationInbox.user_id == user.id
        )
        if unread_only:
            query = query.filter(NotificationInbox.is_read == False)

        notifications = query.order_by(
            NotificationInbox.created_at.desc()
        ).offset(skip).limit(limit).all()

        return notifications

    except Exception as e:
        logger.error(f"Error listing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list notifications.",
        )


@router.get("/count")
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the count of unread notifications for the current user"""
    try:
        count = db.query(NotificationInbox).filter(
            NotificationInbox.user_id == user.id,
            NotificationInbox.is_read == False,
        ).count()
        return {"count": count}

    except Exception as e:
        logger.error(f"Error counting notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to count notifications.",
        )


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a specific notification as read"""
    try:
        notification = db.query(NotificationInbox).filter(
            NotificationInbox.id == notification_id,
            NotificationInbox.user_id == user.id,
        ).first()

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()

        return {"message": "Notification marked as read."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read.",
        )


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all unread notifications as read"""
    try:
        now = datetime.utcnow()
        updated = db.query(NotificationInbox).filter(
            NotificationInbox.user_id == user.id,
            NotificationInbox.is_read == False,
        ).update(
            {"is_read": True, "read_at": now},
            synchronize_session=False,
        )
        db.commit()
        return {"message": f"{updated} notification(s) marked as read."}

    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read.",
        )


@router.get("/brief/night", response_model=NightBriefResponse)
async def get_night_brief(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a Night Brief summary: upcoming deadlines and alerts for the next 24 hours.
    Premium users get instant on-demand access; free users see the same content.
    """
    try:
        now = datetime.utcnow()
        tomorrow = now + timedelta(hours=24)

        # Fetch upcoming DEADLINE events within 24 hours
        deadlines = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.event_type == EventType.DEADLINE,
            AcademicEvent.date_time >= now,
            AcademicEvent.date_time <= tomorrow,
        ).order_by(AcademicEvent.date_time.asc()).all()

        # Fetch active ALERT events (no date constraint — alerts are urgent)
        alerts = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.event_type == EventType.ALERT,
        ).order_by(AcademicEvent.urgency_score.desc()).limit(5).all()

        # Fetch upcoming EVENTs in the next 24 h
        events_query = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.event_type == EventType.EVENT,
            AcademicEvent.date_time >= now,
            AcademicEvent.date_time <= tomorrow,
        ).order_by(AcademicEvent.date_time.asc()).all()

        total_items = len(deadlines) + len(alerts)
        if total_items == 0:
            summary = "You're all caught up! No urgent deadlines or alerts in the next 24 hours."
        else:
            parts = []
            if deadlines:
                parts.append(f"{len(deadlines)} deadline(s) coming up")
            if alerts:
                parts.append(f"{len(alerts)} active alert(s)")
            summary = "Night Brief: " + ", ".join(parts) + ". Stay on top of your academic schedule."

        return {
            "generated_at": now,
            "deadline_count": len(deadlines),
            "alert_count": len(alerts),
            "event_count": len(events_query),
            "upcoming_deadlines": deadlines,
            "active_alerts": alerts,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Error generating night brief: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate Night Brief.",
        )
