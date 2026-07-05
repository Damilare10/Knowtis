"""
Pydantic Schemas for Knowtis API
"""
from pydantic import BaseModel, EmailStr, Field, model_validator
from pydantic import field_serializer
from datetime import datetime
from uuid import UUID
from typing import List, Optional, Any
from app.models import EventType, ReminderState, ResearchHeardAbout
from app.timezone_utils import format_iso_for_api


class _KnowtisBaseModel(BaseModel):
    """Base for all response schemas. Ensures datetimes serialise as
    timezone-aware UTC ISO strings (ending in ``Z``) so the frontend can
    convert to the configured display timezone without ambiguity."""

    @field_serializer("*", when_used="json")
    def _serialize_dt(self, value, _info):
        if isinstance(value, datetime):
            return format_iso_for_api(value)
        return value


# ── User Schemas ──────────────────────────────────────────────────────────────

class UserBase(_KnowtisBaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    fcm_token: Optional[str] = None


class UserRegister(_KnowtisBaseModel):
    """Payload accepted by POST /api/v1/auth/register.

    ``full_name`` is intentionally omitted — the PRD only requires a unique
    username + email for sign-up; the display name can be set later from
    profile settings. ``confirm_password`` is accepted and validated against
    ``password`` server-side so a missing/typo'd confirmation is caught even
    if a client forgets to enforce it.
    """

    email: EmailStr
    username: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r"^[a-z0-9_]+$",
        description="3-20 chars; lowercase letters, digits, and underscores only.",
    )
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    whatsapp_number: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Digits-only E.164 number; cleaned server-side.",
    )

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UsernameCheckResponse(_KnowtisBaseModel):
    """Response for GET /api/v1/auth/check-username."""

    username: str
    available: bool
    suggestion: Optional[str] = None


class UserLogin(_KnowtisBaseModel):
    username: str
    password: str


class UserUpdate(_KnowtisBaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    whatsapp_number: Optional[str] = None
    fcm_token: Optional[str] = None


class UserUpgrade(_KnowtisBaseModel):
    tier: str



class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_premium: bool
    tier: str
    role: str
    auth_provider: str
    created_at: datetime
    ai_tokens_received: int = 0

    class Config:
        from_attributes = True


# ── Token Schemas ─────────────────────────────────────────────────────────────

class TokenResponse(_KnowtisBaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


class RefreshRequest(_KnowtisBaseModel):
    refresh_token: str


# ── Academic Event Schemas ────────────────────────────────────────────────────

class AcademicEventBase(_KnowtisBaseModel):
    event_type: EventType
    course_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    venue: Optional[str] = None
    date_time: Optional[datetime] = None


class AcademicEventCreate(AcademicEventBase):
    pass


class AcademicEventResponse(AcademicEventBase):
    id: UUID
    user_id: UUID
    group_id: Optional[UUID] = None
    reminder_state: ReminderState
    urgency_score: float
    confidence_score: float
    relevance_score: float
    actionability_score: float
    is_duplicate: bool
    canonical_event_id: Optional[UUID] = None
    source_message_id: Optional[str] = None
    source_group_jid: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AcademicEventListResponse(_KnowtisBaseModel):
    items: List[AcademicEventResponse]
    total: int
    skip: int
    limit: int


class SemanticSearchResponse(_KnowtisBaseModel):
    event: AcademicEventResponse
    similarity: float

    class Config:
        from_attributes = True


# ── Reminder Schemas ──────────────────────────────────────────────────────────

class ReminderCreate(_KnowtisBaseModel):
    event_id: UUID
    reminder_type: str = "NOTIFICATION"
    delivery_channel: str = "IN_APP"
    days_before: int = 1
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None


class ReminderResponse(_KnowtisBaseModel):
    id: UUID
    user_id: UUID
    event_id: UUID
    reminder_type: str
    delivery_channel: str
    scheduled_time: Optional[datetime] = None
    is_sent: bool
    sent_at: Optional[datetime] = None
    is_recurring: bool
    recurrence_pattern: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Notification Schemas ──────────────────────────────────────────────────────

class NotificationResponse(_KnowtisBaseModel):
    id: UUID
    user_id: UUID
    event_id: Optional[UUID] = None
    notification_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NightBriefResponse(_KnowtisBaseModel):
    generated_at: datetime
    deadline_count: int
    alert_count: int
    event_count: int
    upcoming_deadlines: List[AcademicEventResponse]
    active_alerts: List[AcademicEventResponse]
    summary: str


# ── WhatsApp Schemas ──────────────────────────────────────────────────────────

class WhatsAppGroupResponse(_KnowtisBaseModel):
    id: UUID
    group_jid: str
    group_name: str
    group_description: Optional[str] = None
    coverage_state: str
    is_active: bool
    join_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class JoinGroupRequest(_KnowtisBaseModel):
    invite_link: str


# ── Calendar Schemas ──────────────────────────────────────────────────────────

class CalendarConnectRequest(_KnowtisBaseModel):
    provider: str  # "google" | "outlook"
    auth_code: str


class CalendarStatusResponse(_KnowtisBaseModel):
    provider: str
    is_active: bool
    last_sync: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── OCR Schemas ───────────────────────────────────────────────────────────────

class OCRExtractResponse(_KnowtisBaseModel):
    extracted_text: str
    events_created: int
    events: List[AcademicEventResponse]
    applied_filters: Optional[str] = None


# ── AI Catch-Up Agent Schemas ────────────────────────────────────────────────
class AIQueryRequest(_KnowtisBaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    course_code: Optional[str] = Field(
        None, max_length=20, description="Optional course filter (e.g. CS101)"
    )
    stream: bool = Field(
        False, description="Stream the conversational answer (premium only)"
    )


class AICitation(_KnowtisBaseModel):
    event_id: UUID
    title: str
    course_code: Optional[str] = None
    date_time: Optional[datetime] = None
    event_type: Optional[str] = None
    venue: Optional[str] = None


class AIRetrievalInfo(_KnowtisBaseModel):
    events_count: int = 0
    reminders_count: int = 0
    notifications_count: int = 0
    ocr_count: int = 0
    sources: List[str] = Field(default_factory=list)


class AIQueryResponse(_KnowtisBaseModel):
    query: str
    answer: str
    tier: str
    mode: str
    citations: List[AICitation] = Field(default_factory=list)
    retrieval: AIRetrievalInfo = Field(default_factory=AIRetrievalInfo)


class ChatMessageResponse(_KnowtisBaseModel):
    id: str
    role: str
    content: str
    day: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ChatHistoryResponse(_KnowtisBaseModel):
    messages: List[ChatMessageResponse] = Field(default_factory=list)
    grouped_by_day: bool = True


class ChatSendRequest(_KnowtisBaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatClearResponse(_KnowtisBaseModel):
    deleted: int


# ── Widget Schemas ───────────────────────────────────────────────────────────

class WidgetEventItem(_KnowtisBaseModel):
    id: UUID
    event_type: str
    course_code: Optional[str] = None
    title: str
    venue: Optional[str] = None
    date_time: Optional[datetime] = None
    urgency_score: float

    class Config:
        from_attributes = True


class WidgetDailyBrief(_KnowtisBaseModel):
    deadlines_today: int
    schedule_changes_today: int
    exam_reminders_today: int
    summary_text: str
    next_event: Optional[WidgetEventItem] = None


class WidgetCascadePayload(_KnowtisBaseModel):
    daily_brief: WidgetDailyBrief
    cascade_events: List[WidgetEventItem]
    recent_alerts: List[WidgetEventItem]


# ── Training & Onboarding Schemas ───────────────────────────────────────────

from enum import Enum

class FeedbackType(str, Enum):
    CONFIRMED_CORRECT = "confirmed_correct"
    CORRECTED = "corrected"
    REPORTED_NOISE = "reported_noise"


class PredictionRecordResponse(_KnowtisBaseModel):
    id: UUID
    user_id: UUID
    raw_message_id: Optional[UUID] = None
    academic_event_id: Optional[UUID] = None
    message_text: str
    predicted_category: Optional[str] = None
    predicted_confidence: Optional[float] = None
    event_type: Optional[str] = None
    event_completeness: Optional[str] = None
    actionability: Optional[str] = None
    needs_review: bool
    field_confidence: Optional[Any] = None
    model_version: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionRecordListResponse(_KnowtisBaseModel):
    items: List[PredictionRecordResponse]
    total: int
    skip: int
    limit: int


class TrainingFeedbackCreate(_KnowtisBaseModel):
    prediction_id: UUID
    feedback_type: FeedbackType
    corrected_category: Optional[str] = None
    corrected_course_code: Optional[str] = None
    corrected_date_time: Optional[datetime] = None
    corrected_event_type: Optional[str] = None
    notes: Optional[str] = None


class TrainingFeedbackResponse(_KnowtisBaseModel):
    id: UUID
    prediction_id: UUID
    user_id: UUID
    feedback_type: FeedbackType
    corrected_category: Optional[str] = None
    corrected_course_code: Optional[str] = None
    corrected_date_time: Optional[datetime] = None
    corrected_event_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ResearchOnboardingRequest(_KnowtisBaseModel):
    heard_about: Optional[ResearchHeardAbout] = None
    primary_use_case: Optional[str] = None
    other_text: Optional[str] = None
    skipped: bool = False


class ResearchOnboardingResponse(_KnowtisBaseModel):
    id: UUID
    user_id: UUID
    heard_about: Optional[ResearchHeardAbout] = None
    primary_use_case: Optional[str] = None
    skipped: bool
    other_text: Optional[str] = None
    completed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchOnboardingStatus(_KnowtisBaseModel):
    completed: bool
    skipped: bool
    heard_about: Optional[ResearchHeardAbout] = None
    primary_use_case: Optional[str] = None


