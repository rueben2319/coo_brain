from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.calendar_event import (
    CalendarEventCreate,
    CalendarEventRead,
    CalendarEventUpdate,
)

router = APIRouter(prefix="/calendar-events", tags=["Calendar Events"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[CalendarEventRead])
async def list_calendar_events(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List internal calendar events for the company."""
    res = (
        db.table("calendar_events")
        .select("*")
        .eq("company_id", str(auth.company_id))
        .order("starts_at", desc=False)
        .execute()
    )
    return [CalendarEventRead(**row) for row in res.data or []]


@router.get("/{event_id}", response_model=CalendarEventRead)
async def get_calendar_event(
    event_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single calendar event."""
    res = (
        db.table("calendar_events")
        .select("*")
        .eq("id", str(event_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found")
    return CalendarEventRead(**res.data[0])


@router.post("", response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
async def create_calendar_event(
    payload: CalendarEventCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Create an internal calendar event record."""
    cid_str = str(auth.company_id)
    created_by = payload.created_by or auth.user_id
    data = {
        "company_id": cid_str,
        "title": payload.title,
        "description": payload.description,
        "starts_at": payload.starts_at.isoformat(),
        "ends_at": payload.ends_at.isoformat() if payload.ends_at else None,
        "related_task_id": str(payload.related_task_id) if payload.related_task_id else None,
        "related_decision_id": str(payload.related_decision_id) if payload.related_decision_id else None,
        "created_by": str(created_by) if created_by else None,
    }
    res = db.table("calendar_events").insert(data).execute()
    return CalendarEventRead(**res.data[0])


@router.patch("/{event_id}", response_model=CalendarEventRead)
async def update_calendar_event(
    event_id: UUID,
    payload: CalendarEventUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Update calendar event details."""
    cid_str = str(auth.company_id)
    check = (
        db.table("calendar_events")
        .select("id")
        .eq("id", str(event_id))
        .eq("company_id", cid_str)
        .execute()
    )
    if not check.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found")

    upd: dict = {}
    if payload.title is not None:
        upd["title"] = payload.title
    if payload.description is not None:
        upd["description"] = payload.description
    if payload.starts_at is not None:
        upd["starts_at"] = payload.starts_at.isoformat()
    if payload.ends_at is not None:
        upd["ends_at"] = payload.ends_at.isoformat()
    if payload.related_task_id is not None:
        upd["related_task_id"] = str(payload.related_task_id)
    if payload.related_decision_id is not None:
        upd["related_decision_id"] = str(payload.related_decision_id)

    if upd:
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = db.table("calendar_events").update(upd).eq("id", str(event_id)).execute()
        return CalendarEventRead(**res.data[0])

    res = db.table("calendar_events").select("*").eq("id", str(event_id)).execute()
    return CalendarEventRead(**res.data[0])


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar_event(
    event_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Delete a calendar event."""
    res = (
        db.table("calendar_events")
        .delete()
        .eq("id", str(event_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found")
    return None
