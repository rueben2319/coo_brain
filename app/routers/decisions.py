from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.decision import (
    DecisionApprove,
    DecisionCreate,
    DecisionRead,
    DecisionReject,
    DecisionStatus,
)
from app.services.decision_engine import DecisionEngineService

router = APIRouter(prefix="/decisions", tags=["Decisions"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[DecisionRead])
async def list_decisions(
    status_filter: Optional[DecisionStatus] = Query(None, alias="status"),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List proposed, approved, and executed decisions."""
    query = db.table("decisions").select("*").eq("company_id", str(auth.company_id))
    if status_filter:
        query = query.eq("status", status_filter.value)
    res = query.order("created_at", desc=True).execute()
    return [DecisionRead(**row) for row in res.data or []]


@router.get("/{decision_id}", response_model=DecisionRead)
async def get_decision(
    decision_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single decision details."""
    res = (
        db.table("decisions")
        .select("*")
        .eq("id", str(decision_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return DecisionRead(**res.data[0])


@router.post("", response_model=DecisionRead, status_code=status.HTTP_201_CREATED)
async def propose_decision(
    payload: DecisionCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Manually propose a decision and evaluate it against approval rules."""
    engine = DecisionEngineService(db)
    proposed_by = auth.user_id or auth.company_id
    return await engine.propose_decision(
        company_id=auth.company_id,
        proposed_by=proposed_by,
        action_type=payload.action_type,
        action_payload=payload.action_payload,
        reasoning=payload.reasoning,
        risk_level=payload.risk_level,
        department_id=payload.department_id,
        related_goal_id=payload.related_goal_id,
    )


@router.post("/{decision_id}/evaluate", response_model=DecisionRead)
async def evaluate_decision(
    decision_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Re-evaluate an existing decision against approval rules."""
    engine = DecisionEngineService(db)
    try:
        return await engine.evaluate_decision(decision_id, auth.company_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{decision_id}/approve", response_model=DecisionRead)
async def approve_decision(
    decision_id: UUID,
    payload: Optional[DecisionApprove] = None,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Approve a decision at pending_human status with role authorization."""
    engine = DecisionEngineService(db)
    approver_id = auth.user_id or auth.company_id
    notes = payload.notes if payload else None
    try:
        return await engine.approve_decision(
            decision_id=decision_id,
            company_id=auth.company_id,
            approver_user_id=approver_id,
            notes=notes,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{decision_id}/reject", response_model=DecisionRead)
async def reject_decision(
    decision_id: UUID,
    payload: DecisionReject,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Reject a decision at pending_human status with mandatory reason."""
    engine = DecisionEngineService(db)
    approver_id = auth.user_id or auth.company_id
    try:
        return await engine.reject_decision(
            decision_id=decision_id,
            company_id=auth.company_id,
            approver_user_id=approver_id,
            notes=payload.notes,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{decision_id}/execute", response_model=DecisionRead)
async def execute_decision(
    decision_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Execute an approved or auto_approved decision and record institutional memory."""
    engine = DecisionEngineService(db)
    try:
        return await engine.execute_decision(
            decision_id=decision_id,
            company_id=auth.company_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Execution error: {str(e)}")
