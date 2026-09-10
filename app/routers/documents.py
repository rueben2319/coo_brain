from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.document import (
    DocumentCreate,
    DocumentRead,
    DocumentUpdate,
    DocumentUploadResponse,
    DocumentChunkRead,
)
from app.services.chunking import chunk_text
from app.services.embedding import get_embedding_service

router = APIRouter(prefix="/documents", tags=["documents"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(auth.token, auth.company_id)


async def _ingest_chunks(
    db: Client,
    company_id: UUID,
    document_id: UUID,
    raw_text: str,
) -> int:
    if not raw_text or not raw_text.strip():
        return 0

    chunks = chunk_text(raw_text)
    if not chunks:
        return 0

    embedding_service = get_embedding_service()
    embeddings = await embedding_service.get_embeddings(chunks)

    rows = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "document_id": str(document_id),
            "company_id": str(company_id),
            "chunk_index": idx,
            "content": chunk,
            "embedding": emb,
        })

    # Batch insert chunks
    if rows:
        db.table("document_chunks").insert(rows).execute()

    return len(rows)


@router.get("", response_model=List[DocumentRead])
async def list_documents(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
    doc_type: Optional[str] = None,
    department_id: Optional[UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.table("documents").select("*").eq("company_id", str(auth.company_id))
    if doc_type:
        query = query.eq("doc_type", doc_type)
    if department_id:
        query = query.eq("department_id", str(department_id))

    res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data or []


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("documents")
        .select("*")
        .eq("id", str(document_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    doc = res.data[0]
    # Count chunks
    chunk_count_res = (
        db.table("document_chunks")
        .select("id", count="exact")
        .eq("document_id", str(document_id))
        .execute()
    )
    doc["chunk_count"] = chunk_count_res.count if chunk_count_res.count is not None else 0
    return doc


@router.get("/{document_id}/chunks", response_model=List[DocumentChunkRead])
async def list_document_chunks(
    document_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    # Verify document belongs to company
    doc_res = (
        db.table("documents")
        .select("id")
        .eq("id", str(document_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not doc_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    res = (
        db.table("document_chunks")
        .select("id, document_id, company_id, chunk_index, content, created_at")
        .eq("document_id", str(document_id))
        .order("chunk_index", desc=False)
        .execute()
    )
    return res.data or []


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """
    Ingests a document: creates document row, chunks the text (~500 tokens),
    embeds each chunk, and inserts into document_chunks.
    """
    data = payload.model_dump(exclude_unset=True, mode="json")
    data["company_id"] = str(auth.company_id)
    if not data.get("uploaded_by") and auth.user_id:
        data["uploaded_by"] = str(auth.user_id)

    raw_text = data.get("raw_text") or ""

    res = db.table("documents").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create document")

    created_doc = res.data[0]
    doc_id = UUID(created_doc["id"])

    # Chunk and embed
    chunks_created = await _ingest_chunks(
        db=db,
        company_id=auth.company_id,
        document_id=doc_id,
        raw_text=raw_text,
    )

    created_doc["chunk_count"] = chunks_created
    return DocumentUploadResponse(
        document=DocumentRead(**created_doc),
        chunks_created=chunks_created,
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """
    Upload a document file (.txt, .md, .csv, etc.). Reads contents,
    stores in documents table, chunks, embeds, and stores in document_chunks.
    """
    content_bytes = await file.read()
    try:
        raw_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = content_bytes.decode("latin-1", errors="ignore")

    doc_title = title or file.filename or "Uploaded Document"
    inferred_type = doc_type or (file.filename.split(".")[-1] if file.filename and "." in file.filename else "text")

    doc_data = {
        "company_id": str(auth.company_id),
        "title": doc_title,
        "doc_type": inferred_type,
        "raw_text": raw_text,
        "uploaded_by": str(auth.user_id) if auth.user_id else None,
    }
    if department_id:
        doc_data["department_id"] = department_id

    res = db.table("documents").insert(doc_data).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create document")

    created_doc = res.data[0]
    doc_id = UUID(created_doc["id"])

    chunks_created = await _ingest_chunks(
        db=db,
        company_id=auth.company_id,
        document_id=doc_id,
        raw_text=raw_text,
    )

    created_doc["chunk_count"] = chunks_created
    return DocumentUploadResponse(
        document=DocumentRead(**created_doc),
        chunks_created=chunks_created,
    )


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True, mode="json")
    data.pop("company_id", None)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    res = (
        db.table("documents")
        .update(data)
        .eq("id", str(document_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # If raw_text was updated, re-chunk and re-embed
    if "raw_text" in data and data["raw_text"]:
        # Delete old chunks
        db.table("document_chunks").delete().eq("document_id", str(document_id)).execute()
        # Ingest new chunks
        await _ingest_chunks(db, auth.company_id, document_id, data["raw_text"])

    return await get_document(document_id, auth, db)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    res = (
        db.table("documents")
        .delete()
        .eq("id", str(document_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return None
