"""
Admin Routes for Knowtis App Owner
Full platform monitoring, user management, group coverage, system health, AI audit, and broadcasting.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.services.whatsapp_service import WhatsAppService
from app.services.notification_service import NotificationService
from app.models import (
    User, UserRole, WhatsAppGroup, AcademicEvent, RawMessage, OCRExtraction,
    Reminder, NotificationInbox, Subscription, SystemHealth,
    ChatMessage, ResearchOnboarding, PredictionRecord, TrainingFeedback,
    WhatsAppAuthState, CoverageState, ProcessingStatus, EventType, ReminderState,
    NotificationTemplate, RateLimitLog
)
from app.schemas import (
    AdminStatsOverview, AdminUserListResponse, UserResponse, AdminUserAdminUpdate,
    AdminGroupStateOverride, AdminBroadcastRequest, PredictionRecordResponse,
    NotificationTemplateCreate, NotificationTemplateUpdate, NotificationTemplateResponse,
    NotificationTemplateListResponse, RateLimitLogResponse, RateLimitLogListResponse,
    RateLimitStatsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/stats", response_model=AdminStatsOverview)
async def get_admin_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get holistic platform KPI statistics for the app owner.
    """
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # 1. User Statistics
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    inactive_users = total_users - active_users
    new_users_24h = db.query(func.count(User.id)).filter(User.created_at >= last_24h).scalar() or 0
    new_users_7d = db.query(func.count(User.id)).filter(User.created_at >= last_7d).scalar() or 0
    free_users = db.query(func.count(User.id)).filter(or_(User.tier == 'free', User.tier == None)).scalar() or 0
    premium_users = db.query(func.count(User.id)).filter(or_(User.tier == 'premium', User.is_premium == True)).scalar() or 0
    
    # Admin users count safely checking enum or string
    admin_users = db.query(func.count(User.id)).filter(
        or_(User.role == UserRole.ADMIN, User.role == "admin")
    ).scalar() or 0

    # 2. WhatsApp Groups Statistics
    total_whatsapp_groups = db.query(func.count(WhatsAppGroup.id)).scalar() or 0
    active_whatsapp_groups = db.query(func.count(WhatsAppGroup.id)).filter(WhatsAppGroup.coverage_state == CoverageState.ACTIVE).scalar() or 0
    degraded_whatsapp_groups = db.query(func.count(WhatsAppGroup.id)).filter(WhatsAppGroup.coverage_state == CoverageState.DEGRADED).scalar() or 0
    paused_whatsapp_groups = db.query(func.count(WhatsAppGroup.id)).filter(WhatsAppGroup.coverage_state == CoverageState.PAUSED).scalar() or 0
    recovering_whatsapp_groups = db.query(func.count(WhatsAppGroup.id)).filter(WhatsAppGroup.coverage_state == CoverageState.RECOVERING).scalar() or 0

    # 3. Message Ingestion
    total_raw_messages = db.query(func.count(RawMessage.id)).scalar() or 0
    processed_messages = db.query(func.count(RawMessage.id)).filter(RawMessage.processing_status == ProcessingStatus.PROCESSED).scalar() or 0
    pending_messages = db.query(func.count(RawMessage.id)).filter(RawMessage.processing_status == ProcessingStatus.PENDING).scalar() or 0
    failed_messages = db.query(func.count(RawMessage.id)).filter(RawMessage.processing_status == ProcessingStatus.FAILED).scalar() or 0

    # 4. Academic Events
    total_events = db.query(func.count(AcademicEvent.id)).scalar() or 0
    
    # Events grouped by event_type
    events_type_rows = db.query(AcademicEvent.event_type, func.count(AcademicEvent.id)).group_by(AcademicEvent.event_type).all()
    events_by_type = {
        (row[0].value if hasattr(row[0], 'value') else str(row[0])): row[1]
        for row in events_type_rows
    }
    
    duplicate_events = db.query(func.count(AcademicEvent.id)).filter(AcademicEvent.is_duplicate == True).scalar() or 0
    archived_events = db.query(func.count(AcademicEvent.id)).filter(AcademicEvent.is_archived == True).scalar() or 0

    # 5. Reminders
    total_reminders = db.query(func.count(Reminder.id)).scalar() or 0
    sent_reminders = db.query(func.count(Reminder.id)).filter(Reminder.is_sent == True).scalar() or 0

    # 6. AI & Tokens
    total_ai_tokens_result = db.query(func.sum(User.ai_tokens_received)).scalar() or 0
    total_chat_messages = db.query(func.count(ChatMessage.id)).scalar() or 0

    # 7. OCR
    ocr_extractions_count = db.query(func.count(OCRExtraction.id)).scalar() or 0

    # 8. Onboarding & Research Stats
    survey_total = db.query(func.count(ResearchOnboarding.id)).scalar() or 0
    survey_skipped = db.query(func.count(ResearchOnboarding.id)).filter(ResearchOnboarding.skipped == True).scalar() or 0
    heard_rows = db.query(ResearchOnboarding.heard_about, func.count(ResearchOnboarding.id)).group_by(ResearchOnboarding.heard_about).all()
    heard_distribution = {
        (row[0].value if hasattr(row[0], 'value') else str(row[0]) if row[0] else 'unspecified'): row[1]
        for row in heard_rows
    }
    
    onboarding_survey_stats = {
        "total_responses": survey_total,
        "skipped_responses": survey_skipped,
        "completed_responses": survey_total - survey_skipped,
        "channels": heard_distribution
    }

    return AdminStatsOverview(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        new_users_24h=new_users_24h,
        new_users_7d=new_users_7d,
        free_users=free_users,
        premium_users=premium_users,
        admin_users=admin_users,
        total_whatsapp_groups=total_whatsapp_groups,
        active_whatsapp_groups=active_whatsapp_groups,
        degraded_whatsapp_groups=degraded_whatsapp_groups,
        paused_whatsapp_groups=paused_whatsapp_groups,
        recovering_whatsapp_groups=recovering_whatsapp_groups,
        total_raw_messages=total_raw_messages,
        processed_messages=processed_messages,
        pending_messages=pending_messages,
        failed_messages=failed_messages,
        total_events=total_events,
        events_by_type=events_by_type,
        duplicate_events=duplicate_events,
        archived_events=archived_events,
        total_reminders=total_reminders,
        sent_reminders=sent_reminders,
        total_ai_tokens=int(total_ai_tokens_result),
        total_chat_messages=total_chat_messages,
        ocr_extractions_count=ocr_extractions_count,
        onboarding_survey_stats=onboarding_survey_stats
    )


@router.get("/users", response_model=AdminUserListResponse)
async def get_admin_users(
    search: Optional[str] = Query(None, description="Search by email, username, or full name"),
    role: Optional[str] = Query(None, description="Filter by role: student, admin"),
    tier: Optional[str] = Query(None, description="Filter by tier: free, premium"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Search and filter registered users for admin management.
    """
    query = db.query(User)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.email.ilike(s),
                User.username.ilike(s),
                User.full_name.ilike(s)
            )
        )

    if role:
        r_clean = role.lower().strip()
        if r_clean == "admin":
            query = query.filter(or_(User.role == UserRole.ADMIN, User.role == "admin"))
        elif r_clean == "student":
            query = query.filter(or_(User.role == UserRole.STUDENT, User.role == "student"))

    if tier:
        t_clean = tier.lower().strip()
        if t_clean == "premium":
            query = query.filter(or_(User.tier == "premium", User.is_premium == True))
        elif t_clean == "free":
            query = query.filter(or_(User.tier == "free", User.tier == None))

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    items = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()

    return AdminUserListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/users/{user_id}")
async def get_admin_user_details(
    user_id: UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get detailed breakdown of a single user (profile, linked groups, events, reminders, research onboarding).
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    groups = db.query(WhatsAppGroup).filter(WhatsAppGroup.user_id == user_id).all()
    events_count = db.query(func.count(AcademicEvent.id)).filter(AcademicEvent.user_id == user_id).scalar() or 0
    reminders_count = db.query(func.count(Reminder.id)).filter(Reminder.user_id == user_id).scalar() or 0
    messages_count = db.query(func.count(RawMessage.id)).filter(RawMessage.user_id == user_id).scalar() or 0
    onboarding = db.query(ResearchOnboarding).filter(ResearchOnboarding.user_id == user_id).first()

    return {
        "user": UserResponse.model_validate(target_user),
        "statistics": {
            "linked_whatsapp_groups_count": len(groups),
            "academic_events_count": events_count,
            "reminders_count": reminders_count,
            "messages_ingested_count": messages_count
        },
        "whatsapp_groups": [
            {
                "id": str(g.id),
                "group_name": g.group_name,
                "group_jid": g.group_jid,
                "coverage_state": g.coverage_state.value if hasattr(g.coverage_state, 'value') else str(g.coverage_state),
                "is_active": g.is_active,
                "join_date": g.join_date
            }
            for g in groups
        ],
        "onboarding": {
            "heard_about": onboarding.heard_about.value if (onboarding and onboarding.heard_about and hasattr(onboarding.heard_about, 'value')) else (str(onboarding.heard_about) if onboarding and onboarding.heard_about else None),
            "primary_use_case": onboarding.primary_use_case if onboarding else None,
            "skipped": onboarding.skipped if onboarding else None
        } if onboarding else None
    }


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: UUID,
    payload: AdminUserAdminUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Modify user parameters: active state, role (student/admin), tier (free/premium), or AI tokens.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    if payload.role is not None:
        role_clean = payload.role.lower().strip()
        if role_clean == "admin":
            target_user.role = UserRole.ADMIN
        elif role_clean == "student":
            target_user.role = UserRole.STUDENT
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'student' or 'admin'")

    if payload.tier is not None:
        tier_clean = payload.tier.lower().strip()
        if tier_clean not in ["free", "premium"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tier must be 'free' or 'premium'")
        target_user.tier = tier_clean
        target_user.is_premium = (tier_clean == "premium")

    if payload.ai_tokens_received is not None:
        target_user.ai_tokens_received = payload.ai_tokens_received

    target_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target_user)

    logger.info(f"Admin {admin_user.username} updated user {target_user.username} (ID: {user_id})")
    return target_user


@router.get("/whatsapp-groups")
async def get_admin_whatsapp_groups(
    coverage_state: Optional[str] = Query(None, description="Filter by CoverageState: ACTIVE, DEGRADED, PAUSED, RECOVERING"),
    search: Optional[str] = Query(None, description="Search group name or JID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Platform-wide listing of linked WhatsApp groups with ownership and message metrics.
    """
    query = db.query(WhatsAppGroup, User).join(User, WhatsAppGroup.user_id == User.id)

    if coverage_state:
        st_clean = coverage_state.upper().strip()
        query = query.filter(WhatsAppGroup.coverage_state == st_clean)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                WhatsAppGroup.group_name.ilike(s),
                WhatsAppGroup.group_jid.ilike(s),
                User.username.ilike(s),
                User.email.ilike(s)
            )
        )

    total = query.count()
    results = query.order_by(desc(WhatsAppGroup.updated_at)).offset(skip).limit(limit).all()

    items = []
    for g, u in results:
        msg_count = db.query(func.count(RawMessage.id)).filter(RawMessage.group_id == g.id).scalar() or 0
        evt_count = db.query(func.count(AcademicEvent.id)).filter(AcademicEvent.group_id == g.id).scalar() or 0

        items.append({
            "id": str(g.id),
            "group_name": g.group_name,
            "group_jid": g.group_jid,
            "group_description": g.group_description,
            "coverage_state": g.coverage_state.value if hasattr(g.coverage_state, 'value') else str(g.coverage_state),
            "is_active": g.is_active,
            "last_coverage_update": g.last_coverage_update,
            "outage_start": g.outage_start,
            "outage_end": g.outage_end,
            "join_attempts": g.join_attempts,
            "join_date": g.join_date,
            "messages_count": msg_count,
            "academic_events_count": evt_count,
            "owner": {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name
            }
        })

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/whatsapp-groups/{group_id}/override-state")
async def override_whatsapp_group_state(
    group_id: UUID,
    payload: AdminGroupStateOverride,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Override the coverage state of a specific WhatsApp group.
    """
    group = db.query(WhatsAppGroup).filter(WhatsAppGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp Group not found")

    valid_states = ["ACTIVE", "DEGRADED", "PAUSED", "RECOVERING"]
    st_clean = payload.coverage_state.upper().strip()
    if st_clean not in valid_states:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Coverage state must be one of {valid_states}")

    group.coverage_state = st_clean
    group.last_coverage_update = datetime.utcnow()
    if st_clean == "ACTIVE":
        group.outage_end = datetime.utcnow()
    elif st_clean in ["DEGRADED", "PAUSED"]:
        if not group.outage_start:
            group.outage_start = datetime.utcnow()

    db.commit()
    db.refresh(group)

    logger.info(f"Admin {admin_user.username} overridden group {group.group_name} state to {st_clean}")
    return {
        "id": str(group.id),
        "group_name": group.group_name,
        "coverage_state": group.coverage_state.value if hasattr(group.coverage_state, 'value') else str(group.coverage_state),
        "last_coverage_update": group.last_coverage_update
    }


@router.get("/system/health")
async def get_admin_system_health(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Real-time diagnostic health check for database, redis, celery worker, WhatsApp session, OCR engines, and background scheduler.
    """
    # 1. Database Health Check
    db_healthy = True
    db_detail = "Database connection operational"
    try:
        db.execute(select(1))
    except Exception as exc:
        db_healthy = False
        db_detail = str(exc)

    # 2. Redis & Celery Check
    from app.redis_client import HAS_REDIS, check_redis_health
    redis_healthy, redis_detail = check_redis_health() if HAS_REDIS else (False, "redis python library not installed")

    # 3. WhatsApp Auth State Session
    auth_state_row = db.query(WhatsAppAuthState).filter(WhatsAppAuthState.id == 1).first()
    whatsapp_auth_exists = bool(auth_state_row and auth_state_row.state)
    whatsapp_last_updated = auth_state_row.last_updated if auth_state_row else None

    # 4. OCR Engines Check
    from app.services.ocr_service import HAS_TESSERACT, HAS_PADDLE, HAS_CV2

    # 5. Background Scheduler Check
    from app.scheduler import _scheduler, HAS_APSCHEDULER
    scheduler_running = bool(HAS_APSCHEDULER and _scheduler and _scheduler.running)

    # 6. Fetch recent logs from system_health table
    recent_health_logs = db.query(SystemHealth).order_by(desc(SystemHealth.checked_at)).limit(10).all()

    return {
        "overall_status": "healthy" if (db_healthy and redis_healthy) else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "components": {
            "database": {
                "healthy": db_healthy,
                "detail": db_detail
            },
            "redis_celery": {
                "healthy": redis_healthy,
                "detail": redis_detail
            },
            "whatsapp_connector_auth": {
                "authenticated": whatsapp_auth_exists,
                "last_updated": whatsapp_last_updated.isoformat() + "Z" if whatsapp_last_updated else None
            },
            "scheduler": {
                "running": scheduler_running
            },
            "ocr_engines": {
                "paddle_ocr": HAS_PADDLE,
                "tesseract_ocr": HAS_TESSERACT,
                "opencv": HAS_CV2
            }
        },
        "recent_system_health_logs": [
            {
                "id": str(h.id),
                "service_name": h.service_name,
                "service_status": h.service_status,
                "message": h.message,
                "checked_at": h.checked_at.isoformat() + "Z" if h.checked_at else None
            }
            for h in recent_health_logs
        ]
    }


@router.get("/ai/predictions")
async def get_admin_ai_predictions_audit(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    needs_review: Optional[bool] = Query(None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    AI Classification model prediction log audit and feedback metrics.
    """
    query = db.query(PredictionRecord)
    if needs_review is not None:
        query = query.filter(PredictionRecord.needs_review == needs_review)

    total = query.count()
    records = query.order_by(desc(PredictionRecord.created_at)).offset(skip).limit(limit).all()

    total_feedback = db.query(func.count(TrainingFeedback.id)).scalar() or 0
    feedback_breakdown_rows = db.query(TrainingFeedback.feedback_type, func.count(TrainingFeedback.id)).group_by(TrainingFeedback.feedback_type).all()
    feedback_breakdown = {row[0]: row[1] for row in feedback_breakdown_rows}

    return {
        "predictions": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "message_text": r.message_text,
                "predicted_category": r.predicted_category,
                "predicted_confidence": r.predicted_confidence,
                "event_type": r.event_type,
                "needs_review": r.needs_review,
                "model_version": r.model_version,
                "created_at": r.created_at
            }
            for r in records
        ],
        "total_predictions": total,
        "feedback_summary": {
            "total_feedback": total_feedback,
            "breakdown": feedback_breakdown
        },
        "skip": skip,
        "limit": limit
    }


@router.post("/ai/predictions/{prediction_id}/review")
async def review_admin_ai_prediction(
    prediction_id: UUID,
    payload: dict,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Confirm or correct an AI prediction record as an admin.
    """
    record = db.query(PredictionRecord).filter(PredictionRecord.id == prediction_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction record not found")

    action = payload.get("action", "confirm")
    corrected_category = payload.get("category")

    record.needs_review = False
    if action == "correct" and corrected_category:
        record.predicted_category = corrected_category

    feedback_type = "confirmed_correct" if action == "confirm" else "corrected"
    feedback = TrainingFeedback(
        prediction_id=record.id,
        user_id=admin_user.id,
        feedback_type=feedback_type,
        corrected_category=corrected_category,
        notes="Reviewed via Admin Board"
    )
    db.add(feedback)

    db.commit()
    db.refresh(record)

    logger.info(f"Admin {admin_user.username} reviewed prediction {record.id} (action: {action})")
    return {
        "id": str(record.id),
        "needs_review": record.needs_review,
        "predicted_category": record.predicted_category,
        "status": "success"
    }



@router.post("/broadcast")
async def broadcast_system_notification(
    payload: AdminBroadcastRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Broadcast a system announcement notification to users (in-app notification inbox).
    Target tier options: 'all' / 'everyone', 'free', 'premium'.
    """
    user_query = db.query(User).filter(User.is_active == True)

    target_t = (payload.target_tier or "all").lower().strip()
    if target_t == "free":
        user_query = user_query.filter(or_(User.tier == "free", User.tier == None))
    elif target_t == "premium":
        user_query = user_query.filter(or_(User.tier == "premium", User.is_premium == True))
    # 'all' or 'everyone' targets all active users

    recipient_users = user_query.all()
    if not recipient_users:
        return {"sent_count": 0, "message": "No matching active users found for broadcast"}

    sent_count = 0
    for u in recipient_users:
        notification = NotificationService.dispatch(
            user_id=u.id,
            notification_type="SYSTEM_BROADCAST",
            title=payload.title,
            description=payload.description,
            db=db,
            alert_level="info",
            is_urgent=False,
        )
        if notification:
            # Trigger native push and in-app for broadcast
            NotificationService._schedule_push(
                u.id,
                {
                    "type": "broadcast",
                    "title": payload.title,
                    "description": payload.description,
                    "notification_id": str(notification.id),
                }
            )
            sent_count += 1

    logger.info(f"Admin {admin_user.username} broadcasted notification '{payload.title}' to {sent_count} users")
    return {
        "sent_count": sent_count,
        "target_tier": payload.target_tier,
        "title": payload.title
    }


# ── Notification Templates ──────────────────────────────────────────────────────

@router.get("/notification-templates", response_model=NotificationTemplateListResponse)
async def list_notification_templates(
    search: Optional[str] = Query(None, description="Search by name or category"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all notification templates with search and filtering.
    """
    query = db.query(NotificationTemplate)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                NotificationTemplate.name.ilike(s),
                NotificationTemplate.category.ilike(s)
            )
        )

    if category:
        query = query.filter(NotificationTemplate.category == category)

    if is_active is not None:
        query = query.filter(NotificationTemplate.is_active == is_active)

    total = query.count()
    items = query.order_by(desc(NotificationTemplate.updated_at)).offset(skip).limit(limit).all()

    return NotificationTemplateListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.post("/notification-templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_template(
    payload: NotificationTemplateCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new notification template.
    Variables in templates use {{variable_name}} syntax.
    """
    template = NotificationTemplate(
        **payload.model_dump(),
        created_by=admin_user.id
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    logger.info(f"Admin {admin_user.username} created notification template '{template.name}'")
    return template


@router.get("/notification-templates/{template_id}", response_model=NotificationTemplateResponse)
async def get_notification_template(
    template_id: UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get a single notification template by ID.
    """
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.put("/notification-templates/{template_id}", response_model=NotificationTemplateResponse)
async def update_notification_template(
    template_id: UUID,
    payload: NotificationTemplateUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update a notification template.
    """
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(template)

    logger.info(f"Admin {admin_user.username} updated notification template '{template.name}'")
    return template


@router.delete("/notification-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_template(
    template_id: UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a notification template.
    """
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    db.delete(template)
    db.commit()

    logger.info(f"Admin {admin_user.username} deleted notification template '{template.name}'")


@router.post("/notification-templates/{template_id}/test")
async def test_notification_template(
    template_id: UUID,
    variables: dict = {},
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Preview a notification template with provided variables.
    """
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    # Simple template rendering
    def render(tmpl: str, vars: dict) -> str:
        result = tmpl
        for k, v in vars.items():
            result = result.replace(f"{{{{{k}}}}}", str(v))
        return result

    return {
        "title": render(template.title_template, variables),
        "body": render(template.body_template, variables),
        "variables_used": list(variables.keys()),
        "missing_variables": [v for v in template.variables if v not in variables]
    }


# ── Rate Limit Dashboard ────────────────────────────────────────────────────────

@router.get("/rate-limit/logs", response_model=RateLimitLogListResponse)
async def list_rate_limit_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    blocked_only: bool = Query(False, description="Show only blocked requests"),
    start_date: Optional[datetime] = Query(None, description="Filter from date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter to date (ISO format)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List rate limit log entries with filtering.
    """
    query = db.query(RateLimitLog)

    if user_id:
        query = query.filter(RateLimitLog.user_id == user_id)
    if ip_address:
        query = query.filter(RateLimitLog.ip_address == ip_address)
    if endpoint:
        query = query.filter(RateLimitLog.endpoint.ilike(f"%{endpoint}%"))
    if blocked_only:
        query = query.filter(RateLimitLog.blocked == True)
    if start_date:
        query = query.filter(RateLimitLog.created_at >= start_date)
    if end_date:
        query = query.filter(RateLimitLog.created_at <= end_date)

    total = query.count()
    items = query.order_by(desc(RateLimitLog.created_at)).offset(skip).limit(limit).all()

    return RateLimitLogListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/rate-limit/stats", response_model=RateLimitStatsResponse)
async def get_rate_limit_stats(
    hours: int = Query(24, ge=1, le=168, description="Hours of history to analyze"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get aggregated rate limit statistics for the dashboard.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # Base query for the time window
    base_query = db.query(RateLimitLog).filter(RateLimitLog.created_at >= since)

    total_requests = base_query.count()
    blocked_requests = base_query.filter(RateLimitLog.blocked == True).count()

    # Unique users and IPs
    unique_users = base_query.filter(RateLimitLog.user_id.isnot(None)).with_entities(func.count(func.distinct(RateLimitLog.user_id))).scalar() or 0
    unique_ips = base_query.filter(RateLimitLog.ip_address.isnot(None)).with_entities(func.count(func.distinct(RateLimitLog.ip_address))).scalar() or 0

    # Top endpoints by request count
    top_endpoints_rows = base_query.with_entities(
        RateLimitLog.endpoint,
        func.count(RateLimitLog.id).label('count')
    ).group_by(RateLimitLog.endpoint).order_by(desc('count')).limit(10).all()
    top_endpoints = [{"endpoint": row[0], "count": row[1]} for row in top_endpoints_rows]

    # Top blocked endpoints
    top_blocked_rows = base_query.filter(RateLimitLog.blocked == True).with_entities(
        RateLimitLog.endpoint,
        func.count(RateLimitLog.id).label('count')
    ).group_by(RateLimitLog.endpoint).order_by(desc('count')).limit(10).all()
    top_blocked_endpoints = [{"endpoint": row[0], "count": row[1]} for row in top_blocked_rows]

    # By tier
    by_tier_rows = base_query.with_entities(
        RateLimitLog.user_tier,
        func.count(RateLimitLog.id).label('count')
    ).group_by(RateLimitLog.user_tier).all()
    by_tier = {row[0] or "unknown": row[1] for row in by_tier_rows}

    # By hour (for chart)
    by_hour_rows = base_query.with_entities(
        func.date_trunc('hour', RateLimitLog.created_at).label('hour'),
        func.count(RateLimitLog.id).label('count')
    ).group_by('hour').order_by('hour').all()
    by_hour = [{"hour": row[0].isoformat() + "Z" if row[0] else None, "count": row[1]} for row in by_hour_rows]

    return RateLimitStatsResponse(
        total_requests=total_requests,
        blocked_requests=blocked_requests,
        unique_users=unique_users,
        unique_ips=unique_ips,
        top_endpoints=top_endpoints,
        top_blocked_endpoints=top_blocked_endpoints,
        by_tier=by_tier,
        by_hour=by_hour
    )


@router.delete("/rate-limit/logs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_rate_limit_logs(
    older_than_days: int = Query(30, ge=1, le=365, description="Delete logs older than N days"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete old rate limit logs (cleanup).
    """
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    deleted = db.query(RateLimitLog).filter(RateLimitLog.created_at < cutoff).delete()
    db.commit()

    logger.info(f"Admin {admin_user.username} cleared {deleted} rate limit log entries older than {older_than_days} days")


# ── WhatsApp Connector & QR Code Management ────────────────────────────────────

@router.get("/whatsapp/connector-status")
async def get_whatsapp_connector_status(
    admin_user: User = Depends(require_admin)
):
    """
    Get live connection state and latest QR code from WhatsApp Baileys connector.
    """
    return WhatsAppService.get_status()


@router.post("/whatsapp/generate-qr")
async def generate_whatsapp_connector_qr(
    admin_user: User = Depends(require_admin)
):
    """
    Trigger fresh QR code generation on the WhatsApp Baileys connector.
    Returns 409 with action guidance if already connected or needs reset.
    """
    result = WhatsAppService.generate_qr()
    if not result.get("success"):
        action = result.get("action")
        if action == "disconnect":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": result["message"],
                    "action": "disconnect",
                    "status": result.get("status")
                }
            )
        if action == "reset":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": result["message"],
                    "action": "reset",
                    "status": result.get("status")
                }
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.get("message", "WhatsApp connector error")
        )
    return result


@router.post("/whatsapp/reset")
async def reset_whatsapp_connector_session(
    admin_user: User = Depends(require_admin)
):
    """
    Wipe persisted Baileys auth state and restart session to get a fresh QR code.
    """
    return WhatsAppService.reset_session()


@router.post("/whatsapp/disconnect")
async def disconnect_whatsapp_connector_session(
    admin_user: User = Depends(require_admin)
):
    """
    Disconnect current active WhatsApp session.
    """
    return WhatsAppService.disconnect_session()


# ── Gate Visibility Routes ───────────────────────────────────────────────────────

@router.get("/gates")
async def get_gate_state(
    admin_user: User = Depends(require_admin)
):
    """
    Return current submission gate state (quarantine records, failures, cooldowns).
    """
    from app.services.submission_gate_service import SubmissionGateService
    from app.services.ci_gate_service import CiGateService
    return {
        "submission_gate": SubmissionGateService.state(),
    }


@router.post("/gates/reset")
async def reset_gate_state(
    source_key: Optional[str] = None,
    admin_user: User = Depends(require_admin)
):
    """
    Reset quarantine / submission gate state for a source (or all if none given).
    """
    from app.services.submission_gate_service import SubmissionGateService
    SubmissionGateService.reset(source_key=source_key)
    return {"reset": True, "source_key": source_key}


@router.post("/model-verify")
async def verify_model(
    model_path: str = Query(..., description="Path to model directory for verification"),
    strict: bool = True,
    admin_user: User = Depends(require_admin)
):
    """
    Run model-builder verification (approval-stage gate) on a model package.
    """
    from app.services.ci_gate_service import CiGateService
    result = CiGateService.block_if_invalid(model_path, source_key="admin_model_check", strict=strict)
    return result.to_dict()

