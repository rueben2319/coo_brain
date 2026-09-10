from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.report import ReportGenerateRequest, ReportRead, ReportType
from app.services.report_generator import ReportGeneratorService

router = APIRouter(prefix="/reports", tags=["Reports"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[ReportRead])
async def list_reports(
    report_type: Optional[ReportType] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List historical reports for the company."""
    query = db.table("reports").select("*").eq("company_id", str(auth.company_id))
    if report_type:
        query = query.eq("report_type", report_type.value)
    res = query.order("created_at", desc=True).execute()
    return [ReportRead(**row) for row in res.data or []]


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single report by ID."""
    res = (
        db.table("reports")
        .select("*")
        .eq("id", str(report_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ReportRead(**res.data[0])


@router.post("/generate", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def generate_report(
    payload: ReportGenerateRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Synthesize operational snapshot and metrics into a structured markdown report."""
    generator = ReportGeneratorService(db)
    generated_by = auth.user_id or auth.company_id
    try:
        return await generator.generate_report(
            company_id=auth.company_id,
            request=payload,
            generated_by=generated_by,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate report: {str(e)}")


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Delete a report."""
    res = (
        db.table("reports")
        .delete()
        .eq("id", str(report_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return None
