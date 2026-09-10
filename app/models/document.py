from datetime import datetime
from typing import List, Optional
from uuid import UUID
from app.models.common import AppBaseModel


class DocumentBase(AppBaseModel):
    title: str
    doc_type: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: Optional[str] = None
    department_id: Optional[UUID] = None
    uploaded_by: Optional[UUID] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(AppBaseModel):
    title: Optional[str] = None
    doc_type: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: Optional[str] = None
    department_id: Optional[UUID] = None
    uploaded_by: Optional[UUID] = None


class DocumentChunkRead(AppBaseModel):
    id: UUID
    document_id: UUID
    company_id: UUID
    chunk_index: int
    content: str
    similarity: Optional[float] = None
    created_at: datetime


class DocumentRead(DocumentBase):
    id: UUID
    company_id: UUID
    chunk_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(AppBaseModel):
    document: DocumentRead
    chunks_created: int
