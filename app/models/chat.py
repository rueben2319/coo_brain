from datetime import datetime
from typing import List, Optional
from uuid import UUID
from app.models.common import AppBaseModel, MessageRole


class ConversationBase(AppBaseModel):
    title: Optional[str] = None
    employee_id: Optional[UUID] = None


class ConversationCreate(ConversationBase):
    pass


class ConversationRead(ConversationBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime


class MessageBase(AppBaseModel):
    role: MessageRole
    content: str
    cited_document_ids: List[UUID] = []
    cited_memory_ids: List[UUID] = []


class MessageCreate(MessageBase):
    conversation_id: UUID


class MessageRead(MessageBase):
    id: UUID
    conversation_id: UUID
    company_id: UUID
    created_at: datetime


class ChatRequest(AppBaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    employee_id: Optional[UUID] = None


class ChatResponse(AppBaseModel):
    conversation_id: UUID
    message_id: UUID
    reply: str
    cited_document_ids: List[UUID] = []
    cited_memory_ids: List[UUID] = []
    retrieved_documents_count: int = 0
    retrieved_memories_count: int = 0
