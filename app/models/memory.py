from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import Field
from app.models.common import AppBaseModel, MemoryType


class MemoryEntryBase(AppBaseModel):
    memory_type: MemoryType
    summary: str
    detail: Optional[str] = None
    related_goal_id: Optional[UUID] = None
    related_department_id: Optional[UUID] = None
    importance: int = Field(default=3, ge=1, le=5)
    occurred_at: Optional[datetime] = None


class MemoryEntryCreate(MemoryEntryBase):
    pass


class MemoryEntryUpdate(AppBaseModel):
    memory_type: Optional[MemoryType] = None
    summary: Optional[str] = None
    detail: Optional[str] = None
    related_goal_id: Optional[UUID] = None
    related_department_id: Optional[UUID] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    occurred_at: Optional[datetime] = None


class MemoryEntryRead(MemoryEntryBase):
    id: UUID
    company_id: UUID
    similarity: Optional[float] = None
    created_at: datetime
