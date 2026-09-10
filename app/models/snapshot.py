from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CompanyStateSnapshotBase(BaseModel):
    metrics: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None


class CompanyStateSnapshotCreate(CompanyStateSnapshotBase):
    company_id: Optional[UUID] = None
    generated_by: Optional[UUID] = None


class CompanyStateSnapshotRead(CompanyStateSnapshotBase):
    id: UUID
    company_id: UUID
    generated_by: Optional[UUID] = None
    created_at: datetime
