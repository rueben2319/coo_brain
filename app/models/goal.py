from datetime import date, datetime
from typing import Optional
from uuid import UUID
from app.models.common import AppBaseModel, GoalStatus


class GoalBase(AppBaseModel):
    title: str
    description: Optional[str] = None
    metric_name: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    unit: Optional[str] = None
    status: GoalStatus = GoalStatus.not_started
    department_id: Optional[UUID] = None
    parent_goal_id: Optional[UUID] = None
    starts_at: Optional[date] = None
    due_at: Optional[date] = None
    created_by: Optional[UUID] = None


class GoalCreate(GoalBase):
    pass


class GoalUpdate(AppBaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    metric_name: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    unit: Optional[str] = None
    status: Optional[GoalStatus] = None
    department_id: Optional[UUID] = None
    parent_goal_id: Optional[UUID] = None
    starts_at: Optional[date] = None
    due_at: Optional[date] = None
    created_by: Optional[UUID] = None


class GoalRead(GoalBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
