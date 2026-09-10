from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.common import AppBaseModel



class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    AUTO_APPROVED = "auto_approved"
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class DecisionBase(BaseModel):
    action_type: str
    action_payload: Dict[str, Any] = Field(default_factory=dict)
    reasoning: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    department_id: Optional[UUID] = None
    related_goal_id: Optional[UUID] = None


class DecisionCreate(DecisionBase):
    company_id: Optional[UUID] = None
    proposed_by: Optional[UUID] = None


class DecisionUpdate(BaseModel):
    status: Optional[DecisionStatus] = None
    decision_notes: Optional[str] = None
    decided_by: Optional[UUID] = None
    decided_at: Optional[datetime] = None


class DecisionApprove(BaseModel):
    notes: Optional[str] = None


class DecisionReject(BaseModel):
    notes: str = Field(..., description="Reason for rejection is required")


class DecisionRead(DecisionBase, AppBaseModel):
    id: UUID
    company_id: UUID
    proposed_by: UUID
    matched_policy_id: Optional[UUID] = None
    status: DecisionStatus
    decided_by: Optional[UUID] = None
    decided_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    executed_at: Optional[datetime] = None
    outcome: Optional[str] = None
    created_at: datetime
    updated_at: datetime



class ApprovalRuleRead(BaseModel):
    id: UUID
    company_id: UUID
    action_type: str
    max_risk: RiskLevel
    max_amount: Optional[float] = None
    currency: Optional[str] = None
    required_approver_role: Optional[str] = None
    auto_approve: bool = False
    is_active: bool = True
    created_at: datetime
