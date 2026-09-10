from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.task import TaskCreate, TaskPriority, TaskRead, TaskStatus, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[TaskRead])
async def list_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    assigned_to: Optional[UUID] = Query(None),
    department_id: Optional[UUID] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List tasks for the company with optional filters."""
    query = db.table("tasks").select("*").eq("company_id", str(auth.company_id))
    if status_filter:
        query = query.eq("status", status_filter.value)
    if assigned_to:
        query = query.eq("assigned_to", str(assigned_to))
    if department_id:
        query = query.eq("department_id", str(department_id))
    res = query.order("created_at", desc=True).execute()
    return [TaskRead(**row) for row in res.data or []]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single task details."""
    res = (
        db.table("tasks")
        .select("*")
        .eq("id", str(task_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead(**res.data[0])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Create a new task."""
    cid_str = str(auth.company_id)
    created_by = payload.created_by or auth.user_id
    task_data = {
        "company_id": cid_str,
        "title": payload.title,
        "description": payload.description,
        "assigned_to": str(payload.assigned_to) if payload.assigned_to else None,
        "department_id": str(payload.department_id) if payload.department_id else None,
        "priority": payload.priority.value,
        "status": payload.status.value,
        "due_at": payload.due_at.isoformat() if payload.due_at else None,
        "related_decision_id": str(payload.related_decision_id) if payload.related_decision_id else None,
        "related_goal_id": str(payload.related_goal_id) if payload.related_goal_id else None,
        "created_by": str(created_by) if created_by else None,
    }
    res = db.table("tasks").insert(task_data).execute()
    return TaskRead(**res.data[0])


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Update task properties or status."""
    cid_str = str(auth.company_id)
    check = (
        db.table("tasks")
        .select("id")
        .eq("id", str(task_id))
        .eq("company_id", cid_str)
        .execute()
    )
    if not check.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    upd: dict = {}
    if payload.title is not None:
        upd["title"] = payload.title
    if payload.description is not None:
        upd["description"] = payload.description
    if payload.assigned_to is not None:
        upd["assigned_to"] = str(payload.assigned_to)
    if payload.department_id is not None:
        upd["department_id"] = str(payload.department_id)
    if payload.priority is not None:
        upd["priority"] = payload.priority.value
    if payload.status is not None:
        upd["status"] = payload.status.value
        if payload.status == TaskStatus.DONE and not payload.completed_at:
            upd["completed_at"] = datetime.now(timezone.utc).isoformat()
    if payload.due_at is not None:
        upd["due_at"] = payload.due_at.isoformat()
    if payload.completed_at is not None:
        upd["completed_at"] = payload.completed_at.isoformat()

    if upd:
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = db.table("tasks").update(upd).eq("id", str(task_id)).execute()
        return TaskRead(**res.data[0])

    res = db.table("tasks").select("*").eq("id", str(task_id)).execute()
    return TaskRead(**res.data[0])


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Delete a task."""
    res = (
        db.table("tasks")
        .delete()
        .eq("id", str(task_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return None
