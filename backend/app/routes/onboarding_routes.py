"""
Post-registration onboarding routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ResearchOnboarding, ResearchHeardAbout, User
from app.routes.events_routes import get_current_user
from app.schemas import (
    ResearchOnboardingRequest,
    ResearchOnboardingResponse,
    ResearchOnboardingStatus,
)


router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])


def _completed(record: ResearchOnboarding | None) -> bool:
    return bool(record and (record.skipped or (record.heard_about and record.primary_use_case)))


@router.get("/research", response_model=ResearchOnboardingStatus)
async def get_research_onboarding(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return whether the current user has completed research onboarding."""
    record = db.query(ResearchOnboarding).filter(ResearchOnboarding.user_id == user.id).first()
    return {
        "completed": _completed(record),
        "skipped": bool(record and record.skipped),
        "heard_about": record.heard_about if record else None,
        "primary_use_case": record.primary_use_case if record else None,
    }


@router.post("/research", response_model=ResearchOnboardingResponse)
async def save_research_onboarding(
    payload: ResearchOnboardingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update the current user's research onboarding answers."""
    if not payload.skipped and (not payload.heard_about or not payload.primary_use_case):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="heard_about and primary_use_case are required unless skipped is true",
        )
    if payload.heard_about != ResearchHeardAbout.OTHER and payload.other_text:
        payload.other_text = None

    record = db.query(ResearchOnboarding).filter(ResearchOnboarding.user_id == user.id).first()
    if not record:
        record = ResearchOnboarding(user_id=user.id)
        db.add(record)

    record.heard_about = payload.heard_about
    record.primary_use_case = payload.primary_use_case
    record.skipped = payload.skipped
    record.other_text = payload.other_text[:255] if payload.other_text else None

    db.commit()
    db.refresh(record)

    return ResearchOnboardingResponse(
        id=record.id,
        user_id=record.user_id,
        heard_about=record.heard_about,
        primary_use_case=record.primary_use_case,
        skipped=record.skipped,
        other_text=record.other_text,
        completed=_completed(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
