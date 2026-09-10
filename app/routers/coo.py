from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ConversationRead,
    MessageRead,
)
from app.services.brain import BrainService

router = APIRouter(prefix="/coo", tags=["coo-brain"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


# 5. The chat endpoint — the actual "Brain"
@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def coo_chat(
    payload: ChatRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """
    The Executive COO Brain:
    - Embeds user message
    - Performs cosine similarity search for documents & memory entries
    - Retrieves structured goals and policies
    - Synthesizes advisory response with Ollama Cloud
    - Saves messages and returns reply with cited document and memory IDs
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty",
        )

    brain_service = BrainService(db)
    return await brain_service.execute_chat(
        auth=auth,
        message=payload.message.strip(),
        conversation_id=payload.conversation_id,
        employee_id=payload.employee_id,
    )


@router.get("/conversations", response_model=List[ConversationRead])
async def list_conversations(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    res = (
        db.table("coo_conversations")
        .select("*")
        .eq("company_id", str(auth.company_id))
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return res.data or []


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("coo_conversations")
        .select("*")
        .eq("id", str(conversation_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return res.data[0]


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageRead])
async def list_conversation_messages(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    # Verify conversation belongs to company
    conv_res = (
        db.table("coo_conversations")
        .select("id")
        .eq("id", str(conversation_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not conv_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    res = (
        db.table("coo_messages")
        .select("*")
        .eq("conversation_id", str(conversation_id))
        .eq("company_id", str(auth.company_id))
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []
