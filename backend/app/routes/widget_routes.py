"""
API Routes - Widgets
Supplies data specifically formatted for the Android homescreen widgets.
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AcademicEvent, EventType, User
from app.dependencies import get_current_user, get_user_tier
from app.schemas import WidgetCascadePayload, WidgetDailyBrief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widgets", tags=["Widgets"])


@router.get("/android", response_model=WidgetCascadePayload)
async def get_android_widget_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregated data for the Android widgets (Daily Brief & Cascade).
    Free tier limits cascade_events to 3 items, premium up to 10.
    """
    try:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # 1. Fetch counts for today's summary
        deadlines_today = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.event_type == EventType.DEADLINE,
            AcademicEvent.date_time >= today_start,
            AcademicEvent.date_time < today_end,
            AcademicEvent.is_archived == False,
            or_(AcademicEvent.is_duplicate == False, AcademicEvent.is_duplicate == None)
        ).count()

        schedule_changes_today = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.event_type == EventType.ALERT,
            AcademicEvent.date_time >= today_start,
            AcademicEvent.date_time < today_end,
            AcademicEvent.is_archived == False,
            or_(AcademicEvent.is_duplicate == False, AcademicEvent.is_duplicate == None)
        ).count()

        exam_reminders_today = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.event_type == EventType.DEADLINE,
            AcademicEvent.date_time >= today_start,
            AcademicEvent.date_time < today_end,
            AcademicEvent.is_archived == False,
            or_(AcademicEvent.is_duplicate == False, AcademicEvent.is_duplicate == None),
            or_(
                AcademicEvent.title.ilike("%exam%"),
                AcademicEvent.title.ilike("%quiz%"),
                AcademicEvent.title.ilike("%test%"),
                AcademicEvent.description.ilike("%exam%"),
                AcademicEvent.description.ilike("%quiz%"),
                AcademicEvent.description.ilike("%test%")
            )
        ).count()

        # 2. Get Next Upcoming Event
        next_event = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.date_time >= now,
            AcademicEvent.is_archived == False,
            or_(AcademicEvent.is_duplicate == False, AcademicEvent.is_duplicate == None)
        ).order_by(AcademicEvent.date_time.asc()).first()

        # Build summary text
        summary_parts = []
        if deadlines_today > 0:
            summary_parts.append(f"{deadlines_today} deadline{'s' if deadlines_today > 1 else ''} today")
        if schedule_changes_today > 0:
            summary_parts.append(f"{schedule_changes_today} change{'s' if schedule_changes_today > 1 else ''} today")
        if not summary_parts:
            summary_parts.append("No deadlines today")
        
        summary_text = " • ".join(summary_parts)
        if next_event:
            time_str = next_event.date_time.strftime("%H:%M")
            course_str = f"{next_event.course_code} " if next_event.course_code else ""
            summary_text += f" • Next: {course_str}{next_event.title} at {time_str}"

        daily_brief = WidgetDailyBrief(
            deadlines_today=deadlines_today,
            schedule_changes_today=schedule_changes_today,
            exam_reminders_today=exam_reminders_today,
            summary_text=summary_text,
            next_event=next_event
        )

        # 3. Get Cascade Events (ordered by urgency desc, then date_time asc)
        # Exclude INFO type
        tier = get_user_tier(user)
        limit = 3 if tier == "free" else 10

        cascade_events = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.is_archived == False,
            or_(AcademicEvent.is_duplicate == False, AcademicEvent.is_duplicate == None),
            AcademicEvent.event_type != EventType.INFO
        ).order_by(
            AcademicEvent.urgency_score.desc(),
            AcademicEvent.date_time.asc()
        ).limit(limit).all()

        # 4. Get Recent Alerts (last 48 hours)
        recent_alerts = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user.id,
            AcademicEvent.event_type == EventType.ALERT,
            AcademicEvent.is_archived == False,
            or_(AcademicEvent.is_duplicate == False, AcademicEvent.is_duplicate == None),
            AcademicEvent.created_at >= now - timedelta(days=2)
        ).order_by(AcademicEvent.created_at.desc()).limit(5).all()

        return WidgetCascadePayload(
            daily_brief=daily_brief,
            cascade_events=cascade_events,
            recent_alerts=recent_alerts
        )

    except Exception as e:
        logger.error(f"Error fetching widget data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch widget data."
        )
