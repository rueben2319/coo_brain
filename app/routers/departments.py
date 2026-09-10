from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.department import DepartmentCreate, DepartmentRead, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["departments"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


@router.get("", response_model=List[DepartmentRead])
async def list_departments(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    res = (
        db.table("departments")
        .select("*")
        .eq("company_id", str(auth.company_id))
        .range(offset, offset + limit - 1)
        .execute()
    )
    return res.data or []


@router.get("/{department_id}", response_model=DepartmentRead)
async def get_department(
    department_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("departments")
        .select("*")
        .eq("id", str(department_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return res.data[0]


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    # Enforce company_id from caller's token
    data["company_id"] = str(auth.company_id)
    res = db.table("departments").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create department")
    return res.data[0]


@router.patch("/{department_id}", response_model=DepartmentRead)
async def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    # Disallow overriding company_id
    data.pop("company_id", None)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    res = (
        db.table("departments")
        .update(data)
        .eq("id", str(department_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return res.data[0]


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("departments")
        .delete()
        .eq("id", str(department_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return None
