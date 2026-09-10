from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.models.common import AppBaseModel


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class NotificationBase(BaseModel):
    recipient_id: UUID
    channel: NotificationChannel = NotificationChannel.IN_APP
    title: str
    body: str
    related_decision_id: Optional[UUID] = None
    related_event_id: Optional[UUID] = None
    related_task_id: Optional[UUID] = None
    status: NotificationStatus = NotificationStatus.PENDING


class NotificationCreate(NotificationBase):
    company_id: Optional[UUID] = None


class NotificationUpdate(BaseModel):
    status: Optional[NotificationStatus] = None
    read_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class NotificationRead(NotificationBase, AppBaseModel):
    id: UUID
    company_id: UUID
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime
