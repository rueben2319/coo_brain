from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import Field
from app.models.common import AppBaseModel


class CompanyBase(AppBaseModel):
    name: str
    industry: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    fiscal_year_start: Optional[date] = None
    timezone: str = "Africa/Blantyre"


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(AppBaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    fiscal_year_start: Optional[date] = None
    timezone: Optional[str] = None


class CompanyRead(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
