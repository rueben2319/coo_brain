from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.models.common import AppBaseModel


class CalendarEventBase(BaseModel):
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    related_task_id: Optional[UUID] = None
    related_decision_id: Optional[UUID] = None


class CalendarEventCreate(CalendarEventBase):
    company_id: Optional[UUID] = None
    created_by: Optional[UUID] = None


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    related_task_id: Optional[UUID] = None
    related_decision_id: Optional[UUID] = None


class CalendarEventRead(CalendarEventBase, AppBaseModel):
    id: UUID
    company_id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
