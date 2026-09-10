from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.event import EventRead, EventSeverity, EventStatus, EventUpdate

router = APIRouter(prefix="/events", tags=["Events"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[EventRead])
async def list_events(
    severity: Optional[EventSeverity] = None,
    status_filter: Optional[EventStatus] = Query(None, alias="status"),
    source_agent_id: Optional[UUID] = None,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List event signals detected by agents."""
    query = db.table("events").select("*").eq("company_id", str(auth.company_id))

    if severity:
        query = query.eq("severity", severity.value)
    if status_filter:
        query = query.eq("status", status_filter.value)
    if source_agent_id:
        query = query.eq("source_agent_id", str(source_agent_id))

    res = query.order("detected_at", desc=True).execute()
    return [EventRead(**row) for row in res.data or []]


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single event detail."""
    res = (
        db.table("events")
        .select("*")
        .eq("id", str(event_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventRead(**res.data[0])


@router.patch("/{event_id}", response_model=EventRead)
async def update_event_status(
    event_id: UUID,
    payload: EventUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Update event status (e.g. acknowledge, resolve, dismiss)."""
    cid_str = str(auth.company_id)
    existing = (
        db.table("events")
        .select("id")
        .eq("id", str(event_id))
        .eq("company_id", cid_str)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    update_dict = payload.model_dump(exclude_unset=True)
    if payload.status == EventStatus.RESOLVED and "resolved_at" not in update_dict:
        update_dict["resolved_at"] = datetime.now(timezone.utc).isoformat()

    if "status" in update_dict and isinstance(update_dict["status"], EventStatus):
        update_dict["status"] = update_dict["status"].value

    res = (
        db.table("events")
        .update(update_dict)
        .eq("id", str(event_id))
        .eq("company_id", cid_str)
        .execute()
    )
    return EventRead(**res.data[0])
