from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.purchase_request import (
    PurchaseRequestApprove,
    PurchaseRequestCreate,
    PurchaseRequestRead,
    PurchaseRequestReject,
    PurchaseRequestStatus,
    PurchaseRequestUpdate,
)
from app.services.decision_engine import ROLE_HIERARCHY

router = APIRouter(prefix="/purchase-requests", tags=["Purchase Requests"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


def _resolve_employee(db: Client, company_id: UUID, user_id: UUID):
    cid_str = str(company_id)
    uid_str = str(user_id)
    res = db.table("employees").select("*").eq("company_id", cid_str).eq("id", uid_str).execute()
    if res.data:
        return res.data[0]
    res = db.table("employees").select("*").eq("company_id", cid_str).eq("auth_user_id", uid_str).execute()
    if res.data:
        return res.data[0]
    res = db.table("employees").select("*").eq("company_id", cid_str).eq("is_active", True).in_("role", ["owner", "executive"]).limit(1).execute()
    if res.data:
        return res.data[0]
    return None


@router.get("", response_model=List[PurchaseRequestRead])
async def list_purchase_requests(
    status_filter: Optional[PurchaseRequestStatus] = Query(None, alias="status"),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List purchase requests for company."""
    query = db.table("purchase_requests").select("*").eq("company_id", str(auth.company_id))
    if status_filter:
        query = query.eq("status", status_filter.value)
    res = query.order("created_at", desc=True).execute()
    return [PurchaseRequestRead(**row) for row in res.data or []]


@router.get("/{pr_id}", response_model=PurchaseRequestRead)
async def get_purchase_request(
    pr_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single purchase request."""
    res = (
        db.table("purchase_requests")
        .select("*")
        .eq("id", str(pr_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    return PurchaseRequestRead(**res.data[0])


@router.post("", response_model=PurchaseRequestRead, status_code=status.HTTP_201_CREATED)
async def create_purchase_request(
    payload: PurchaseRequestCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Create a new purchase request."""
    cid_str = str(auth.company_id)
    req_by = payload.requested_by or auth.user_id
    data = {
        "company_id": cid_str,
        "department_id": str(payload.department_id) if payload.department_id else None,
        "requested_by": str(req_by) if req_by else None,
        "vendor": payload.vendor,
        "description": payload.description,
        "amount": payload.amount,
        "currency": payload.currency,
        "status": payload.status.value,
        "related_decision_id": str(payload.related_decision_id) if payload.related_decision_id else None,
        "related_policy_id": str(payload.related_policy_id) if payload.related_policy_id else None,
        "notes": payload.notes,
    }
    res = db.table("purchase_requests").insert(data).execute()
    return PurchaseRequestRead(**res.data[0])


@router.post("/{pr_id}/approve", response_model=PurchaseRequestRead)
async def approve_purchase_request(
    pr_id: UUID,
    payload: Optional[PurchaseRequestApprove] = None,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Approve purchase request with explicit human authority."""
    cid_str = str(auth.company_id)
    pr_res = (
        db.table("purchase_requests")
        .select("*")
        .eq("id", str(pr_id))
        .eq("company_id", cid_str)
        .execute()
    )
    if not pr_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase request not found")

    pr = pr_res.data[0]
    if pr.get("status") not in [PurchaseRequestStatus.DRAFT.value, PurchaseRequestStatus.PENDING_APPROVAL.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve purchase request with status '{pr.get('status')}'.",
        )

    approver = _resolve_employee(db, auth.company_id, auth.user_id or auth.company_id)
    if not approver:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Approving employee record not found.")

    approver_role = approver.get("role", "staff")
    required_role = "executive" if float(pr.get("amount", 0)) > 50000 else "manager"
    if ROLE_HIERARCHY.get(approver_role, 0) < ROLE_HIERARCHY.get(required_role, 2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{approver_role}' is not authorized to approve this purchase request. Required role: '{required_role}'.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    notes = payload.notes if payload else None
    upd_data = {
        "status": PurchaseRequestStatus.APPROVED.value,
        "approved_by": approver["id"],
        "approved_at": now_iso,
        "notes": notes or pr.get("notes"),
    }
    upd_res = (
        db.table("purchase_requests")
        .update(upd_data)
        .eq("id", str(pr_id))
        .execute()
    )
    return PurchaseRequestRead(**upd_res.data[0])


@router.post("/{pr_id}/reject", response_model=PurchaseRequestRead)
async def reject_purchase_request(
    pr_id: UUID,
    payload: PurchaseRequestReject,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Reject purchase request with reason."""
    cid_str = str(auth.company_id)
    pr_res = (
        db.table("purchase_requests")
        .select("*")
        .eq("id", str(pr_id))
        .eq("company_id", cid_str)
        .execute()
    )
    if not pr_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase request not found")

    pr = pr_res.data[0]
    if pr.get("status") not in [PurchaseRequestStatus.DRAFT.value, PurchaseRequestStatus.PENDING_APPROVAL.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject purchase request with status '{pr.get('status')}'.",
        )

    approver = _resolve_employee(db, auth.company_id, auth.user_id or auth.company_id)
    if not approver:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Approving employee record not found.")

    now_iso = datetime.now(timezone.utc).isoformat()
    upd_data = {
        "status": PurchaseRequestStatus.REJECTED.value,
        "approved_by": approver["id"],
        "approved_at": now_iso,
        "notes": payload.notes,
    }
    upd_res = (
        db.table("purchase_requests")
        .update(upd_data)
        .eq("id", str(pr_id))
        .execute()
    )
    return PurchaseRequestRead(**upd_res.data[0])
