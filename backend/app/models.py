"""
SQLAlchemy ORM Models for Knowtis
Comprehensive database schema with validation
"""

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Date, Float, Integer, ForeignKey,
    JSON, Enum as SQLEnum, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum

from app.database import Base


class EventType(str, Enum):
    """Academic event type enumeration"""
    DEADLINE = "DEADLINE"
    EVENT = "EVENT"
    ALERT = "ALERT"
    INFO = "INFO"


class UserRole(str, Enum):
    """User roles for authentication and authorization"""
    STUDENT = "student"
    ADMIN = "admin"


class CoverageState(str, Enum):
    """WhatsApp group coverage state"""
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"


class ReminderState(str, Enum):
    """Reminder state enumeration"""
    PENDING = "PENDING"
    REMINDED = "REMINDED"
    DISMISSED = "DISMISSED"
    COMPLETED = "COMPLETED"


class ProcessingStatus(str, Enum):
    """Message processing status"""
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class User(Base):
    """User Account Model"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255))
    full_name = Column(String(255))
    profile_picture_url = Column(Text)
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    auth_provider = Column(String(50), default="email")
    auth_provider_id = Column(String(255))
    tier = Column(String(20), default="free")
    role = Column(SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    whatsapp_number = Column(String(50), unique=True, nullable=True, index=True)
    fcm_token = Column(String(255), nullable=True)
    ai_tokens_received = Column(Integer, default=0, nullable=False)

    # Relationships
    whatsapp_groups = relationship("WhatsAppGroup", back_populates="user", cascade="all, delete-orphan")
    academic_events = relationship("AcademicEvent", back_populates="user", cascade="all, delete-orphan")
    raw_messages = relationship("RawMessage", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("NotificationInbox", back_populates="user", cascade="all, delete-orphan")
    calendar_syncs = relationship("CalendarSync", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("WhatsAppSession", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


    __table_args__ = (
        Index("idx_users_auth_provider", "auth_provider", "auth_provider_id"),
    )


class WhatsAppGroup(Base):
    """Linked WhatsApp Groups"""
    __tablename__ = "whatsapp_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_jid = Column(String(255), nullable=False)
    group_name = Column(String(255), nullable=False)
    group_description = Column(Text)
    group_picture_url = Column(Text)
    coverage_state = Column(SQLEnum(CoverageState), default=CoverageState.ACTIVE, index=True)
    last_coverage_update = Column(DateTime)
    outage_start = Column(DateTime)
    outage_end = Column(DateTime)
    is_active = Column(Boolean, default=True)
    join_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="whatsapp_groups")
    academic_events = relationship("AcademicEvent", back_populates="group", cascade="all, delete-orphan")
    raw_messages = relationship("RawMessage", back_populates="group", cascade="all, delete-orphan")
    ocr_extractions = relationship("OCRExtraction", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_group_jid", "user_id", "group_jid", unique=True),
    )


class AcademicEvent(Base):
    """Extracted Academic Events"""
    __tablename__ = "academic_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    course_code = Column(String(50), index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    venue = Column(String(255))
    date_time = Column(DateTime, index=True)
    reminder_state = Column(SQLEnum(ReminderState), default=ReminderState.PENDING)
    urgency_score = Column(Float, default=0.5)
    confidence_score = Column(Float, default=0.8)
    relevance_score = Column(Float, default=0.7)
    actionability_score = Column(Float, default=0.6)
    is_duplicate = Column(Boolean, default=False)
    canonical_event_id = Column(UUID(as_uuid=True), ForeignKey("academic_events.id", ondelete="SET NULL"))
    embedding = Column(String)  # Vector embedding stored as string (to be indexed with pgvector)
    source_message_id = Column(String(255))
    source_group_jid = Column(String(255))
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="academic_events")
    group = relationship("WhatsAppGroup", back_populates="academic_events")
    reminders = relationship("Reminder", back_populates="event", cascade="all, delete-orphan")
    notifications = relationship("NotificationInbox", back_populates="event")


class RawMessage(Base):
    """Raw WhatsApp Messages (Audit Trail)"""
    __tablename__ = "raw_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String(255))
    sender_jid = Column(String(255))
    sender_name = Column(String(255))
    message_text = Column(Text)
    message_type = Column(String(50))
    has_media = Column(Boolean, default=False)
    classification = Column(String(50), index=True)
    confidence_score = Column(Float)
    processing_status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="raw_messages")
    group = relationship("WhatsAppGroup", back_populates="raw_messages")


class OCRExtraction(Base):
    """OCR Extraction Results"""
    __tablename__ = "ocr_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=True)
    message_id = Column(String(255))
    extracted_text = Column(Text, nullable=False)
    extraction_confidence = Column(Float)
    extraction_strategy = Column(String(50))
    user_instructions = Column(Text)
    filtered_events = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    group = relationship("WhatsAppGroup", back_populates="ocr_extractions")


class Reminder(Base):
    """Reminders for Academic Events"""
    __tablename__ = "reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("academic_events.id", ondelete="CASCADE"), nullable=False)
    reminder_type = Column(String(50), default="NOTIFICATION")
    scheduled_time = Column(DateTime, index=True)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    delivery_channel = Column(String(50), default="IN_APP")
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="reminders")
    event = relationship("AcademicEvent", back_populates="reminders")


class NotificationInbox(Base):
    """In-App Notification Inbox"""
    __tablename__ = "notification_inbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("academic_events.id", ondelete="SET NULL"))
    notification_type = Column(String(50))
    title = Column(String(500))
    description = Column(Text)
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")
    event = relationship("AcademicEvent", back_populates="notifications")


class CalendarSync(Base):
    """Calendar Integration (Google, Outlook)"""
    __tablename__ = "calendar_syncs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    calendar_provider = Column(String(50), nullable=False)
    calendar_id = Column(String(255))
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="calendar_syncs")


class Subscription(Base):
    """User Subscription/Payment Information"""
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    revenuecat_subscription_id = Column(String(255), unique=True)
    tier = Column(String(20), default="free", nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    renewal_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    auto_renew = Column(Boolean, default=True)
    payment_provider = Column(String(50))
    price = Column(Float, default=0.0)
    currency = Column(String(10), default="NGN")
    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscriptions")


class WhatsAppSession(Base):
    """WhatsApp Session Management"""
    __tablename__ = "whatsapp_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False)
    session_status = Column(String(50), default="ACTIVE", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sessions")


class RefreshToken(Base):
    """Refresh Token Store for secure token rotation"""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_revoked", "user_id", "revoked"),
    )


class SystemHealth(Base):
    """System Health Monitoring"""
    __tablename__ = "system_health"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(100), index=True)
    service_status = Column(String(50))
    message = Column(Text)
    checked_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    """Persistent AI conversation messages (user questions, AI replies, daily briefs)."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant' | 'brief'
    content = Column(Text, nullable=False)
    day = Column(Date, default=datetime.utcnow().date, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="chat_messages")


class StudentKnowledgeBase(Base):
    """Per-student course dictionary used to enrich extracted entities.

    The NER service resolves raw course codes / abbreviations against this
    table to attach full course titles and lecturer names to events.
    """
    __tablename__ = "student_knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_code = Column(String(20), nullable=False, index=True)
    full_name = Column(String(200))
    lecturer_name = Column(String(200))
    abbreviations = Column(JSON, default=list)  # e.g. ["data structures", "dsa"]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_student_kb_user_course", "user_id", "course_code", unique=True),
    )


class SourceReliability(Base):
    """Cached per-sender reliability used by the confidence scorer.

    Course reps / lecturers accumulate higher reliability than anonymous
    group participants. Defaults to 0.7 when no row exists.
    """
    __tablename__ = "source_reliability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_jid = Column(String(120), nullable=False, index=True)
    sender_name = Column(String(200))
    reliability_score = Column(Float, default=0.7)
    message_count = Column(Integer, default=0)
    is_course_rep = Column(Boolean, default=False)
    is_lecturer = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_source_rel_user_sender", "user_id", "sender_jid", unique=True),
    )


User.chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


class ResearchHeardAbout(str, Enum):
    """How the user heard about Knowtis"""
    FRIEND_OR_CLASSMATE = "friend_or_classmate"
    WHATSAPP_GROUP = "whatsapp_group"
    INSTAGRAM_TIKTOK_X = "instagram_tiktok_x"
    GOOGLE_SEARCH = "google_search"
    CAMPAIGN = "campaign"
    OTHER = "other"


class PredictionRecord(Base):
    """Prediction audit log for offline retraining"""
    __tablename__ = "prediction_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_message_id = Column(UUID(as_uuid=True), ForeignKey("raw_messages.id", ondelete="SET NULL"), nullable=True)
    academic_event_id = Column(UUID(as_uuid=True), ForeignKey("academic_events.id", ondelete="SET NULL"), nullable=True)
    message_text = Column(Text, nullable=False)
    predicted_category = Column(String(50))
    predicted_confidence = Column(Float)
    event_type = Column(String(50))
    event_completeness = Column(String(50))
    actionability = Column(String(50))
    needs_review = Column(Boolean, default=True, index=True)
    field_confidence = Column(JSON)
    model_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    raw_message = relationship("RawMessage")
    academic_event = relationship("AcademicEvent")


class TrainingFeedback(Base):
    """User correction/confirmation for offline training loop"""
    __tablename__ = "training_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_id = Column(UUID(as_uuid=True), ForeignKey("prediction_records.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(String(50), nullable=False)
    corrected_category = Column(String(50))
    corrected_course_code = Column(String(50))
    corrected_date_time = Column(DateTime)
    corrected_event_type = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    prediction = relationship("PredictionRecord")


class ResearchOnboarding(Base):
    """User research onboarding details"""
    __tablename__ = "research_onboardings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    heard_about = Column(SQLEnum(ResearchHeardAbout), nullable=True)
    primary_use_case = Column(String(100), nullable=True)
    skipped = Column(Boolean, default=False, nullable=False)
    other_text = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")

