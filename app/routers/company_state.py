from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.snapshot import CompanyStateSnapshotRead
from app.services.company_state import CompanyStateService

router = APIRouter(prefix="/company-state", tags=["Company State"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("/latest", response_model=CompanyStateSnapshotRead)
async def get_latest_snapshot(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Fetch the most recent point-in-time Company State snapshot."""
    service = CompanyStateService(db)
    snapshot = await service.get_latest_snapshot(auth.company_id)
    if not snapshot:
        # Auto-generate first snapshot if none exists
        snapshot = await service.generate_snapshot(auth.company_id, auth.user_id)
    return snapshot


@router.post("/generate", response_model=CompanyStateSnapshotRead, status_code=status.HTTP_201_CREATED)
async def generate_snapshot(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Trigger generation of a fresh Company State snapshot."""
    service = CompanyStateService(db)
    return await service.generate_snapshot(auth.company_id, auth.user_id)
