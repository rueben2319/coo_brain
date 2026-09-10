import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID
from supabase import Client

from app.config import get_settings

logger = logging.getLogger("coo_brain.retrieval")


@dataclass
class RetrievedDocumentChunk:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    document_title: str
    similarity: float


@dataclass
class RetrievedMemoryEntry:
    id: UUID
    memory_type: str
    summary: str
    detail: Optional[str]
    importance: int
    occurred_at: Optional[str]
    similarity: float


@dataclass
class RetrievalContext:
    company: Dict[str, Any] = field(default_factory=dict)
    document_chunks: List[RetrievedDocumentChunk] = field(default_factory=list)
    memory_entries: List[RetrievedMemoryEntry] = field(default_factory=list)
    goals: List[Dict[str, Any]] = field(default_factory=list)
    policies: List[Dict[str, Any]] = field(default_factory=list)


class RetrievalService:
    def __init__(self, db: Client):
        self.db = db
        self.settings = get_settings()

    async def retrieve_context(
        self,
        company_id: UUID,
        query_embedding: List[float],
        top_k_docs: Optional[int] = None,
        top_k_memories: Optional[int] = None,
    ) -> RetrievalContext:
        top_k_docs = top_k_docs or self.settings.top_k_documents
        top_k_memories = top_k_memories or self.settings.top_k_memories

        context = RetrievalContext()

        # 1. Fetch Company Info (Mission, Vision)
        try:
            res = (
                self.db.table("companies")
                .select("id, name, industry, mission, vision, timezone")
                .eq("id", str(company_id))
                .execute()
            )
            if res.data:
                context.company = res.data[0]
        except Exception as e:
            logger.error(f"Error fetching company info: {e}")

        # 2. Vector Search: Document Chunks via RPC
        try:
            doc_res = self.db.rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": -1.0,
                    "match_count": top_k_docs,
                    "p_company_id": str(company_id),
                },
            ).execute()

            if doc_res.data:
                for row in doc_res.data:
                    context.document_chunks.append(
                        RetrievedDocumentChunk(
                            id=UUID(row["id"]),
                            document_id=UUID(row["document_id"]),
                            chunk_index=row.get("chunk_index", 0),
                            content=row.get("content", ""),
                            document_title=row.get("document_title", "Untitled"),
                            similarity=float(row.get("similarity", 0.0)),
                        )
                    )
        except Exception as e:
            logger.error(f"Error matching document chunks via RPC: {e}")

        # 3. Vector Search: Memory Entries via RPC
        try:
            mem_res = self.db.rpc(
                "match_memory_entries",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": -1.0,
                    "match_count": top_k_memories,
                    "p_company_id": str(company_id),
                },
            ).execute()

            if mem_res.data:
                for row in mem_res.data:
                    context.memory_entries.append(
                        RetrievedMemoryEntry(
                            id=UUID(row["id"]),
                            memory_type=row.get("memory_type", "observation"),
                            summary=row.get("summary", ""),
                            detail=row.get("detail"),
                            importance=row.get("importance", 3),
                            occurred_at=str(row.get("occurred_at", "")),
                            similarity=float(row.get("similarity", 0.0)),
                        )
                    )
        except Exception as e:
            logger.error(f"Error matching memory entries via RPC: {e}")

        # 4. Fetch Active Goals (Structured context)
        try:
            goals_res = (
                self.db.table("goals")
                .select("id, title, description, metric_name, target_value, current_value, unit, status, due_at")
                .eq("company_id", str(company_id))
                .not_.in_("status", ["achieved", "abandoned"])
                .limit(20)
                .execute()
            )
            if goals_res.data:
                context.goals = goals_res.data
        except Exception as e:
            logger.error(f"Error fetching active goals: {e}")

        # 5. Fetch Active Policies (Structured context)
        try:
            policies_res = (
                self.db.table("policies")
                .select("id, title, policy_type, description, rule, is_active, effective_from, effective_to")
                .eq("company_id", str(company_id))
                .eq("is_active", True)
                .limit(30)
                .execute()
            )
            if policies_res.data:
                context.policies = policies_res.data
        except Exception as e:
            logger.error(f"Error fetching active policies: {e}")

        return context
