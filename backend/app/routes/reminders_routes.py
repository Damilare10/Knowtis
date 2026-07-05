"""
API Routes - Reminders
All routes backed by ReminderService (real DB operations).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import User
from app.schemas import ReminderCreate, ReminderResponse
from app.dependencies import get_current_user
from app.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reminders", tags=["Reminders"])


@router.get("", response_model=list[ReminderResponse])
async def list_reminders(
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List reminders for the authenticated user"""
    try:
        reminders = ReminderService.get_user_reminders(
            user_id=user.id,
            active_only=active_only,
            limit=limit,
            db=db,
        )
        return reminders

    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list reminders.",
        )


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    body: ReminderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a reminder for an academic event"""
    try:
        if body.is_recurring:
            reminder = ReminderService.create_recurring_reminder(
                user_id=user.id,
                event_id=body.event_id,
                reminder_type=body.reminder_type,
                delivery_channel=body.delivery_channel,
                recurrence_pattern=body.recurrence_pattern or "daily",
                db=db,
            )
        else:
            reminder = ReminderService.create_reminder(
                user_id=user.id,
                event_id=body.event_id,
                reminder_type=body.reminder_type,
                delivery_channel=body.delivery_channel,
                days_before=body.days_before,
                db=db,
            )

        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create reminder. The event may not exist or may not have a scheduled date.",
            )

        return reminder

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create reminder.",
        )


@router.delete("/{reminder_id}")
async def dismiss_reminder(
    reminder_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss (deactivate) a reminder"""
    try:
        from app.models import Reminder
        reminder = db.query(Reminder).filter(
            Reminder.id == reminder_id,
            Reminder.user_id == user.id,
        ).first()

        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found.",
            )

        success = ReminderService.dismiss_reminder(reminder_id=reminder_id, db=db)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to dismiss reminder.",
            )

        return {"message": "Reminder dismissed successfully."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss reminder.",
        )
