from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.notification import (
    NotificationCreate,
    NotificationRead,
    NotificationStatus,
    NotificationUpdate,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[NotificationRead])
async def list_notifications(
    status_filter: Optional[NotificationStatus] = Query(None, alias="status"),
    recipient_id: Optional[UUID] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List notifications for the company."""
    query = db.table("notifications").select("*").eq("company_id", str(auth.company_id))
    if status_filter:
        query = query.eq("status", status_filter.value)
    if recipient_id:
        query = query.eq("recipient_id", str(recipient_id))
    res = query.order("created_at", desc=True).execute()
    return [NotificationRead(**row) for row in res.data or []]


@router.get("/{notif_id}", response_model=NotificationRead)
async def get_notification(
    notif_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single notification."""
    res = (
        db.table("notifications")
        .select("*")
        .eq("id", str(notif_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationRead(**res.data[0])


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: NotificationCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Create a notification record."""
    cid_str = str(auth.company_id)
    notif_data = {
        "company_id": cid_str,
        "recipient_id": str(payload.recipient_id),
        "channel": payload.channel.value,
        "title": payload.title,
        "body": payload.body,
        "related_decision_id": str(payload.related_decision_id) if payload.related_decision_id else None,
        "related_event_id": str(payload.related_event_id) if payload.related_event_id else None,
        "related_task_id": str(payload.related_task_id) if payload.related_task_id else None,
        "status": payload.status.value,
    }
    res = db.table("notifications").insert(notif_data).execute()
    return NotificationRead(**res.data[0])


@router.post("/{notif_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notif_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Mark notification as read."""
    cid_str = str(auth.company_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    res = (
        db.table("notifications")
        .update({"status": NotificationStatus.READ.value, "read_at": now_iso})
        .eq("id", str(notif_id))
        .eq("company_id", cid_str)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationRead(**res.data[0])


@router.delete("/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notif_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Delete a notification."""
    res = (
        db.table("notifications")
        .delete()
        .eq("id", str(notif_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return None
