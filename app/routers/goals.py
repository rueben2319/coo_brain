from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.goal import GoalCreate, GoalRead, GoalUpdate, GoalStatus

router = APIRouter(prefix="/goals", tags=["goals"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


@router.get("", response_model=List[GoalRead])
async def list_goals(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    department_id: Optional[UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.table("goals").select("*").eq("company_id", str(auth.company_id))
    if status_filter:
        query = query.eq("status", status_filter.value)
    if department_id:
        query = query.eq("department_id", str(department_id))

    res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data or []


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(
    goal_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("goals")
        .select("*")
        .eq("id", str(goal_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return res.data[0]


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data["company_id"] = str(auth.company_id)
    if not data.get("created_by") and auth.user_id:
        data["created_by"] = str(auth.user_id)
    res = db.table("goals").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create goal")
    return res.data[0]


@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(
    goal_id: UUID,
    payload: GoalUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data.pop("company_id", None)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    res = (
        db.table("goals")
        .update(data)
        .eq("id", str(goal_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return res.data[0]


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("goals")
        .delete()
        .eq("id", str(goal_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return None
