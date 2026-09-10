from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.models.common import AppBaseModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: Optional[UUID] = None
    department_id: Optional[UUID] = None
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    due_at: Optional[datetime] = None
    related_decision_id: Optional[UUID] = None
    related_goal_id: Optional[UUID] = None


class TaskCreate(TaskBase):
    company_id: Optional[UUID] = None
    created_by: Optional[UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[UUID] = None
    department_id: Optional[UUID] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskRead(TaskBase, AppBaseModel):
    id: UUID
    company_id: UUID
    created_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
