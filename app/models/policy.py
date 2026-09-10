from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field
from app.models.common import AppBaseModel, PolicyType


class PolicyBase(AppBaseModel):
    title: str
    policy_type: PolicyType
    description: Optional[str] = None
    rule: Dict[str, Any] = Field(default_factory=dict)
    department_id: Optional[UUID] = None
    is_active: bool = True
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    created_by: Optional[UUID] = None


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(AppBaseModel):
    title: Optional[str] = None
    policy_type: Optional[PolicyType] = None
    description: Optional[str] = None
    rule: Optional[Dict[str, Any]] = None
    department_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    created_by: Optional[UUID] = None


class PolicyRead(PolicyBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
