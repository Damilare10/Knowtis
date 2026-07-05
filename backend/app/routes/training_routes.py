"""
API routes for the production feedback loop used by offline classifier training.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PredictionRecord, TrainingFeedback, User
from app.routes.events_routes import get_current_user
from app.schemas import (
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
    """Store a user correction/confirmation for later offline retraining."""
    prediction = db.query(PredictionRecord).filter(
        PredictionRecord.id == payload.prediction_id,
        PredictionRecord.user_id == user.id,
    ).first()
    if not prediction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

    feedback = TrainingFeedback(
        prediction_id=payload.prediction_id,
        user_id=user.id,
        feedback_type=payload.feedback_type,
        corrected_category=payload.corrected_category,
        corrected_course_code=payload.corrected_course_code,
        corrected_date_time=payload.corrected_date_time,
        corrected_event_type=payload.corrected_event_type,
        notes=payload.notes,
    )
    db.add(feedback)

    if payload.feedback_type.value == "confirmed_correct":
        prediction.needs_review = False

    db.commit()
    db.refresh(feedback)
    return feedback
