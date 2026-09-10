from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.company import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


@router.get("", response_model=List[CompanyRead])
async def list_companies(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List caller's company (scoped strictly by caller's JWT company_id)."""
    res = db.table("companies").select("*").eq("id", str(auth.company_id)).execute()
    return res.data or []


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    if company_id != auth.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another company's data",
        )
    res = db.table("companies").select("*").eq("id", str(company_id)).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return res.data[0]


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    res = db.table("companies").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create company")
    return res.data[0]


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    if company_id != auth.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot modify another company's data",
        )
    data = payload.model_dump(exclude_unset=True, mode="json")
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    res = db.table("companies").update(data).eq("id", str(company_id)).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return res.data[0]


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    if company_id != auth.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot delete another company",
        )
    res = db.table("companies").delete().eq("id", str(company_id)).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return None
