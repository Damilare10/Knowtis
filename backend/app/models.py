"""
SQLAlchemy ORM Models for Knowtis
Comprehensive database schema with validation
"""

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Float, Integer, ForeignKey,
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    whatsapp_groups = relationship("WhatsAppGroup", back_populates="user", cascade="all, delete-orphan")
    academic_events = relationship("AcademicEvent", back_populates="user", cascade="all, delete-orphan")
    raw_messages = relationship("RawMessage", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("NotificationInbox", back_populates="user", cascade="all, delete-orphan")
    calendar_syncs = relationship("CalendarSync", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("WhatsAppSession", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_auth_provider", "auth_provider", "auth_provider_id"),
    )


class WhatsAppGroup(Base):
    """Linked WhatsApp Groups"""
    __tablename__ = "whatsapp_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_jid = Column(String(255), unique=True, nullable=False)
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
    group_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=False)
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


class SystemHealth(Base):
    """System Health Monitoring"""
    __tablename__ = "system_health"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(100), index=True)
    service_status = Column(String(50))
    message = Column(Text)
    checked_at = Column(DateTime, default=datetime.utcnow)
