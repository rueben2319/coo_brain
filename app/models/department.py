from datetime import datetime
from typing import Optional
from uuid import UUID
from app.models.common import AppBaseModel


class DepartmentBase(AppBaseModel):
    name: str
    description: Optional[str] = None
    parent_department_id: Optional[UUID] = None
    head_employee_id: Optional[UUID] = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(AppBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_department_id: Optional[UUID] = None
    head_employee_id: Optional[UUID] = None


class DepartmentRead(DepartmentBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
