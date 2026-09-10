from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate, EmployeeRole

router = APIRouter(prefix="/employees", tags=["employees"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


@router.get("", response_model=List[EmployeeRead])
async def list_employees(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    role: Optional[EmployeeRole] = None,
    department_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.table("employees").select("*").eq("company_id", str(auth.company_id))
    if role:
        query = query.eq("role", role.value)
    if department_id:
        query = query.eq("department_id", str(department_id))
    if is_active is not None:
        query = query.eq("is_active", is_active)

    res = query.range(offset, offset + limit - 1).execute()
    return res.data or []


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(
    employee_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("employees")
        .select("*")
        .eq("id", str(employee_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return res.data[0]


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data["company_id"] = str(auth.company_id)
    res = db.table("employees").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create employee")
    return res.data[0]


@router.patch("/{employee_id}", response_model=EmployeeRead)
async def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data.pop("company_id", None)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    res = (
        db.table("employees")
        .update(data)
        .eq("id", str(employee_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return res.data[0]


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("employees")
        .delete()
        .eq("id", str(employee_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return None
