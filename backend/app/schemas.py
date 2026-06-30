"""
Pydantic Schemas for Knowtis API
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID
from typing import List, Optional
from app.models import EventType, ReminderState

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserRegister(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_premium: bool
    tier: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

# Token Schemas
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

# Academic Event Schemas
class AcademicEventBase(BaseModel):
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
    embedding: Optional[str] = None
    source_message_id: Optional[str] = None
    source_group_jid: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class AcademicEventListResponse(BaseModel):
    items: List[AcademicEventResponse]
    total: int
    skip: int
    limit: int
