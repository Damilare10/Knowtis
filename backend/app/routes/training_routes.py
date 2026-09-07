"""
API routes for the production feedback loop used by offline classifier training.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AcademicEvent, PredictionRecord, TrainingFeedback, User
from app.routes.events_routes import get_current_user
from app.schemas import (
    FeedbackType,
    PredictionRecordListResponse,
    TrainingFeedbackCreate,
    TrainingFeedbackResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/training", tags=["Training Feedback"])


@router.get("/predictions", response_model=PredictionRecordListResponse)
async def list_predictions(
    needs_review: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List this user's prediction records for review/confirmation UI."""
    query = db.query(PredictionRecord).filter(PredictionRecord.user_id == user.id)
    if needs_review is not None:
        query = query.filter(PredictionRecord.needs_review == needs_review)

    total = query.count()
    items = query.order_by(PredictionRecord.created_at.desc()).offset(skip).limit(limit).all()
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/feedback", response_model=TrainingFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: TrainingFeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store a user correction/confirmation for later offline retraining and clear review flag."""
    prediction = None
    if payload.prediction_id:
        prediction = db.query(PredictionRecord).filter(
            PredictionRecord.id == payload.prediction_id,
            PredictionRecord.user_id == user.id,
        ).first()

    target_event = None
    if payload.academic_event_id:
        target_event = db.query(AcademicEvent).filter(
            AcademicEvent.id == payload.academic_event_id,
            AcademicEvent.user_id == user.id,
        ).first()
        if not prediction:
            prediction = db.query(PredictionRecord).filter(
                PredictionRecord.academic_event_id == payload.academic_event_id,
                PredictionRecord.user_id == user.id,
            ).first()

    if not prediction:
        if target_event:
            # Create a synthetic prediction record attached to this academic event
            prediction = PredictionRecord(
                user_id=user.id,
                academic_event_id=target_event.id,
                message_text=target_event.description or target_event.title,
                event_type=str(target_event.event_type),
                needs_review=target_event.needs_review,
            )
            db.add(prediction)
            db.flush()
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction or event not found")

    feedback = TrainingFeedback(
        prediction_id=prediction.id,
        user_id=user.id,
        feedback_type=payload.feedback_type.value if hasattr(payload.feedback_type, "value") else str(payload.feedback_type),
        corrected_category=payload.corrected_category,
        corrected_course_code=payload.corrected_course_code,
        corrected_date_time=payload.corrected_date_time,
        corrected_event_type=payload.corrected_event_type,
        notes=payload.notes,
    )
    db.add(feedback)

    feedback_val = payload.feedback_type.value if hasattr(payload.feedback_type, "value") else str(payload.feedback_type)
    if feedback_val == "confirmed_correct":
        prediction.needs_review = False
        if target_event:
            target_event.needs_review = False
        elif prediction.academic_event_id:
            ev = db.query(AcademicEvent).filter(AcademicEvent.id == prediction.academic_event_id).first()
            if ev:
                ev.needs_review = False

    db.commit()
    db.refresh(feedback)
    return feedback
