from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.common import AppBaseModel


class PurchaseRequestStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PurchaseRequestBase(BaseModel):
    description: str
    amount: float
    currency: str = "MWK"
    vendor: Optional[str] = None
    department_id: Optional[UUID] = None
    requested_by: Optional[UUID] = None
    related_decision_id: Optional[UUID] = None
    related_policy_id: Optional[UUID] = None
    status: PurchaseRequestStatus = PurchaseRequestStatus.DRAFT
    notes: Optional[str] = None


class PurchaseRequestCreate(PurchaseRequestBase):
    company_id: Optional[UUID] = None


class PurchaseRequestUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    vendor: Optional[str] = None
    department_id: Optional[UUID] = None
    status: Optional[PurchaseRequestStatus] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None


class PurchaseRequestApprove(BaseModel):
    notes: Optional[str] = None


class PurchaseRequestReject(BaseModel):
    notes: str = Field(..., description="Reason for rejection is required")


class PurchaseRequestRead(PurchaseRequestBase, AppBaseModel):
    id: UUID
    company_id: UUID
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
