from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.models.common import AppBaseModel


class ReportType(str, Enum):
    WEEKLY_SUMMARY = "weekly_summary"
    GOAL_PROGRESS = "goal_progress"
    FINANCIAL_REVIEW = "financial_review"
    RISK_REVIEW = "risk_review"
    CUSTOM = "custom"


class ReportBase(BaseModel):
    report_type: ReportType
    title: str
    content: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    source_snapshot_id: Optional[UUID] = None


class ReportCreate(ReportBase):
    company_id: Optional[UUID] = None
    generated_by: Optional[UUID] = None


class ReportGenerateRequest(BaseModel):
    report_type: ReportType = ReportType.WEEKLY_SUMMARY
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    title: Optional[str] = None


class ReportRead(ReportBase, AppBaseModel):
    id: UUID
    company_id: UUID
    generated_by: Optional[UUID] = None
    created_at: datetime
