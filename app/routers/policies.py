from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.policy import PolicyCreate, PolicyRead, PolicyUpdate, PolicyType

router = APIRouter(prefix="/policies", tags=["policies"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


@router.get("", response_model=List[PolicyRead])
async def list_policies(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    policy_type: Optional[PolicyType] = None,
    is_active: Optional[bool] = None,
    department_id: Optional[UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.table("policies").select("*").eq("company_id", str(auth.company_id))
    if policy_type:
        query = query.eq("policy_type", policy_type.value)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if department_id:
        query = query.eq("department_id", str(department_id))

    res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data or []


@router.get("/{policy_id}", response_model=PolicyRead)
async def get_policy(
    policy_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("policies")
        .select("*")
        .eq("id", str(policy_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return res.data[0]


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: PolicyCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data["company_id"] = str(auth.company_id)
    if not data.get("created_by") and auth.user_id:
        data["created_by"] = str(auth.user_id)
    res = db.table("policies").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create policy")
    return res.data[0]


@router.patch("/{policy_id}", response_model=PolicyRead)
async def update_policy(
    policy_id: UUID,
    payload: PolicyUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data.pop("company_id", None)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    res = (
        db.table("policies")
        .update(data)
        .eq("id", str(policy_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return res.data[0]


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("policies")
        .delete()
        .eq("id", str(policy_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return None
