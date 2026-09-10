from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EventBase(BaseModel):
    event_type: str
    severity: EventSeverity = EventSeverity.INFO
    title: str
    description: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    related_goal_id: Optional[UUID] = None
    related_department_id: Optional[UUID] = None
    resulting_decision_id: Optional[UUID] = None
    status: EventStatus = EventStatus.NEW


class EventCreate(EventBase):
    company_id: Optional[UUID] = None
    source_agent_id: Optional[UUID] = None


class EventUpdate(BaseModel):
    status: Optional[EventStatus] = None
    description: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    resulting_decision_id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None


class EventRead(EventBase):
    id: UUID
    company_id: UUID
    source_agent_id: Optional[UUID] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    created_at: datetime
