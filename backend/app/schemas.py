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
    notification_advance_hours: int = 3


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
    reason: Optional[str] = None



class UserLogin(_KnowtisBaseModel):
    username: str
    password: str


class UserUpdate(_KnowtisBaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    whatsapp_number: Optional[str] = None
    fcm_token: Optional[str] = None
    notification_advance_hours: Optional[int] = None


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
    notification_advance_hours: int = 3

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


class AcademicEventUpdate(_KnowtisBaseModel):
    title: Optional[str] = None
    course_code: Optional[str] = None
    date_time: Optional[datetime] = None
    venue: Optional[str] = None
    event_type: Optional[EventType] = None


class AcademicEventResponse(AcademicEventBase):
    id: UUID
    user_id: UUID
    group_id: Optional[UUID] = None
    group_name: Optional[str] = None
    status: Optional[str] = "ACTIVE"
    date_precision: Optional[str] = "unknown"
    reminder_state: ReminderState
    urgency_score: float
    confidence_score: float
    relevance_score: float
    actionability_score: float
    is_duplicate: bool
    canonical_event_id: Optional[UUID] = None
    needs_review: bool = True
    source_message_id: Optional[str] = None
    source_group_jid: Optional[str] = None
    is_archived: bool
    revisions: Optional[List[Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AcademicEventListResponse(_KnowtisBaseModel):
    items: List[AcademicEventResponse]
    total: int
    skip: int = 0
    limit: int = 20
    truncated: bool = False
    plan_limit: Optional[int] = None


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
    event: Optional[AcademicEventResponse] = None
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
    added_today_count: int
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
    monitored_keywords: Optional[List[str]] = []
    monitored_courses: Optional[List[str]] = []
    filter_mode: Optional[str] = "ALL"

    class Config:
        from_attributes = True


class UpdateGroupFilterRequest(_KnowtisBaseModel):
    monitored_keywords: Optional[List[str]] = None
    monitored_courses: Optional[List[str]] = None
    filter_mode: Optional[str] = None  # "ALL" | "FILTERED". None means "don't change"


class JoinGroupRequest(_KnowtisBaseModel):
    invite_link: str


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


class ActionConfirmation(_KnowtisBaseModel):
    tool: str
    success: bool
    message: str


class ChatMessageResponse(_KnowtisBaseModel):
    id: str
    role: str
    content: str
    day: Optional[str] = None
    created_at: Optional[str] = None
    actions: Optional[List[ActionConfirmation]] = None

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
    prediction_id: Optional[UUID] = None
    academic_event_id: Optional[UUID] = None
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


# ── Admin Schemas ────────────────────────────────────────────────────────────

class AdminUserAdminUpdate(_KnowtisBaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None
    tier: Optional[str] = None
    ai_tokens_received: Optional[int] = None


class AdminUserListResponse(_KnowtisBaseModel):
    items: List[UserResponse]
    total: int
    skip: int
    limit: int


class AdminStatsOverview(_KnowtisBaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    new_users_24h: int
    new_users_7d: int
    free_users: int
    premium_users: int
    admin_users: int
    
    total_whatsapp_groups: int
    active_whatsapp_groups: int
    degraded_whatsapp_groups: int
    paused_whatsapp_groups: int
    recovering_whatsapp_groups: int
    
    total_raw_messages: int
    processed_messages: int
    pending_messages: int
    failed_messages: int
    
    total_events: int
    events_by_type: dict
    duplicate_events: int
    archived_events: int
    
    total_reminders: int
    sent_reminders: int
    
    total_ai_tokens: int
    total_chat_messages: int
    
    ocr_extractions_count: int
    onboarding_survey_stats: dict


class AdminGroupStateOverride(_KnowtisBaseModel):
    coverage_state: str


class AdminBroadcastRequest(_KnowtisBaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    target_tier: str = Field(default="all")


# ── Notification Template Schemas ───────────────────────────────────────────────

class NotificationTemplateBase(_KnowtisBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    title_template: str = Field(..., min_length=1, max_length=500)
    body_template: str = Field(..., min_length=1)
    variables: List[str] = Field(default_factory=list)
    category: str = Field(default="general")
    is_active: bool = True


class NotificationTemplateCreate(NotificationTemplateBase):
    pass


class NotificationTemplateUpdate(_KnowtisBaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    title_template: Optional[str] = Field(None, min_length=1, max_length=500)
    body_template: Optional[str] = Field(None, min_length=1)
    variables: Optional[List[str]] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class NotificationTemplateResponse(NotificationTemplateBase):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationTemplateListResponse(_KnowtisBaseModel):
    items: List[NotificationTemplateResponse]
    total: int
    skip: int
    limit: int


# ── Rate Limit Dashboard Schemas ────────────────────────────────────────────────

class RateLimitLogResponse(_KnowtisBaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    endpoint: str
    method: str
    limit_key: str
    limit_rule: str
    current_count: int
    limit_max: int
    blocked: bool
    user_tier: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RateLimitLogListResponse(_KnowtisBaseModel):
    items: List[RateLimitLogResponse]
    total: int
    skip: int
    limit: int


class RateLimitStatsResponse(_KnowtisBaseModel):
    total_requests: int
    blocked_requests: int
    unique_users: int
    unique_ips: int
    top_endpoints: List[dict]
    top_blocked_endpoints: List[dict]
    by_tier: dict
    by_hour: List[dict]


# ── Structured AI Extraction Schemas ──────────────────────────────────────────

class ExtractedEventItem(BaseModel):
    action_type: str = Field(default="CREATE", description="CREATE (new event), UPDATE (reschedule/venue/deadline change), or CANCEL (cancelled/postponed)")
    category: Optional[str] = Field(default="INFO", description="DEADLINE, EVENT, ALERT, or INFO")
    course_code: Optional[str] = Field(default=None, description="Uppercase normalized course code like CSC301")
    title: str = Field(default="Academic Update", description="Concise info card title (max 80 chars)")
    description: Optional[str] = Field(default=None, description="Extracted event details")
    venue: Optional[str] = Field(default=None, description="Location or venue")
    date_expression: Optional[str] = Field(default=None, description="The temporal phrase exactly as written, e.g. 'next friday 2pm'. Resolved downstream by TemporalParser.")
    date_is_explicit: bool = Field(default=False, description="True when the message states a date or day; False for vague terms like 'soon'")
    # Deprecated: models are no longer asked for a resolved date, because LLM
    # date arithmetic is unverifiable and untestable. Accepted for one release
    # so an older prompt response does not hard-fail validation; ignored by
    # _wrap_batch_result, which logs when it appears.
    date_time: Optional[str] = Field(default=None, description="DEPRECATED, ignored. Use date_expression.")
    lecturer: Optional[str] = Field(default=None, description="Lecturer or instructor name")
    # Deprecated: urgency is derived locally from time-to-deadline by
    # urgency_service, never taken from the model.
    urgency_score: float = Field(default=0.5, ge=0.0, le=1.0, description="DEPRECATED, ignored.")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    actionability_score: float = Field(default=0.6, ge=0.0, le=1.0)
    needs_review: bool = Field(default=False)
    event_completeness: str = Field(default="complete", description="complete, missing_course, missing_date, etc.")


class SingleMessageAIResponse(BaseModel):
    classification: str = Field(default="NOISE", description="SIGNAL or NOISE")
    events: List[ExtractedEventItem] = Field(default_factory=list, description="Array of extracted events for SIGNAL messages")


class BatchMessageAIItem(BaseModel):
    index: int = Field(..., description="Message number / index in batch")
    classification: str = Field(default="NOISE", description="SIGNAL or NOISE")
    events: List[ExtractedEventItem] = Field(default_factory=list, description="Array of extracted events")


class BatchMessageAIResponse(BaseModel):
    items: List[BatchMessageAIItem] = Field(default_factory=list)




