from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import EmailStr
from app.models.common import AppBaseModel, EmployeeRole


class EmployeeBase(AppBaseModel):
    full_name: str
    email: Optional[str] = None
    role: EmployeeRole = EmployeeRole.staff
    title: Optional[str] = None
    department_id: Optional[UUID] = None
    reports_to_id: Optional[UUID] = None
    auth_user_id: Optional[UUID] = None
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(AppBaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[EmployeeRole] = None
    title: Optional[str] = None
    department_id: Optional[UUID] = None
    reports_to_id: Optional[UUID] = None
    auth_user_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class EmployeeRead(EmployeeBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
