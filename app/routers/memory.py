from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.memory import (
    MemoryEntryCreate,
    MemoryEntryRead,
    MemoryEntryUpdate,
    MemoryType,
)
from app.services.embedding import get_embedding_service

router = APIRouter(prefix="", tags=["memory"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


async def _save_memory_entry(
    payload: MemoryEntryCreate,
    auth: AuthContext,
    db: Client,
) -> MemoryEntryRead:
    data = payload.model_dump(exclude_unset=True, mode="json")
    data["company_id"] = str(auth.company_id)

    # Embed the summary field on write
    embedding_service = get_embedding_service()
    embedding = await embedding_service.get_embedding(payload.summary)
    data["embedding"] = embedding

    res = db.table("memory_entries").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create memory entry")

    created = res.data[0]
    # Remove large embedding array before returning model
    created.pop("embedding", None)
    return MemoryEntryRead(**created)


# 4. Memory write endpoint specified in prompt: POST /memory
@router.post("/memory", response_model=MemoryEntryRead, status_code=status.HTTP_201_CREATED)
@router.post("/memory-entries", response_model=MemoryEntryRead, status_code=status.HTTP_201_CREATED)
async def create_memory_entry(
    payload: MemoryEntryCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """
    Records an institutional memory entry (experience/decision/lesson/observation)
    and automatically embeds the summary field into vector(768).
    """
    return await _save_memory_entry(payload, auth, db)


@router.get("/memory", response_model=List[MemoryEntryRead])
@router.get("/memory-entries", response_model=List[MemoryEntryRead])
async def list_memory_entries(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    memory_type: Optional[MemoryType] = None,
    related_goal_id: Optional[UUID] = None,
    related_department_id: Optional[UUID] = None,
    min_importance: Optional[int] = Query(None, ge=1, le=5),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        db.table("memory_entries")
        .select("id, company_id, memory_type, summary, detail, related_goal_id, related_department_id, importance, occurred_at, created_at")
        .eq("company_id", str(auth.company_id))
    )
    if memory_type:
        query = query.eq("memory_type", memory_type.value)
    if related_goal_id:
        query = query.eq("related_goal_id", str(related_goal_id))
    if related_department_id:
        query = query.eq("related_department_id", str(related_department_id))
    if min_importance:
        query = query.gte("importance", min_importance)

    res = query.order("occurred_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data or []


@router.get("/memory/{entry_id}", response_model=MemoryEntryRead)
@router.get("/memory-entries/{entry_id}", response_model=MemoryEntryRead)
async def get_memory_entry(
    entry_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("memory_entries")
        .select("id, company_id, memory_type, summary, detail, related_goal_id, related_department_id, importance, occurred_at, created_at")
        .eq("id", str(entry_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
    return res.data[0]


@router.patch("/memory/{entry_id}", response_model=MemoryEntryRead)
@router.patch("/memory-entries/{entry_id}", response_model=MemoryEntryRead)
async def update_memory_entry(
    entry_id: UUID,
    payload: MemoryEntryUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data.pop("company_id", None)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    if "summary" in data and data["summary"]:
        embedding_service = get_embedding_service()
        data["embedding"] = await embedding_service.get_embedding(data["summary"])

    res = (
        db.table("memory_entries")
        .update(data)
        .eq("id", str(entry_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")

    updated = res.data[0]
    updated.pop("embedding", None)
    return MemoryEntryRead(**updated)


@router.delete("/memory/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/memory-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_entry(
    entry_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("memory_entries")
        .delete()
        .eq("id", str(entry_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
    return None
