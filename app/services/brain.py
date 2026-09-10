from datetime import datetime, timezone
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID
from supabase import Client

from app.auth import AuthContext
from app.models.chat import ChatResponse
from app.services.embedding import get_embedding_service
from app.services.llm import get_llm_service
from app.services.retrieval import RetrievalContext, RetrievalService

logger = logging.getLogger("coo_brain.brain")


def format_system_prompt(
    company_name: str,
    context: RetrievalContext,
    latest_snapshot: Optional[Any] = None,
    open_tasks: Optional[List[Dict[str, Any]]] = None,
    pending_purchase_requests: Optional[List[Dict[str, Any]]] = None,
    pending_decisions: Optional[List[Dict[str, Any]]] = None,
    unread_notifications: Optional[List[Dict[str, Any]]] = None,
) -> str:
    company_info = context.company
    mission = company_info.get("mission") or "Not explicitly defined."
    vision = company_info.get("vision") or "Not explicitly defined."
    industry = company_info.get("industry") or "General Enterprise"

    # Company state snapshot formatting
    snapshot_text = "No point-in-time state snapshot computed yet.\n"
    if latest_snapshot:
        metrics = getattr(latest_snapshot, "metrics", {}) or {}
        summary = getattr(latest_snapshot, "summary", "") or ""
        created_at = getattr(latest_snapshot, "created_at", "")
        snapshot_text = f"Summary ({created_at}): {summary}\nKey Metrics: {json.dumps(metrics)}\n"

    # Goals formatting
    goals_text = ""
    if context.goals:
        for g in context.goals:
            target = f" (Target: {g.get('target_value')} {g.get('unit') or ''})" if g.get("target_value") else ""
            curr = f" [Current: {g.get('current_value')} {g.get('unit') or ''}]" if g.get("current_value") else ""
            goals_text += f"- {g.get('title')}: Status={g.get('status')}{target}{curr}. Due={g.get('due_at')}\n"
    else:
        goals_text = "None recorded.\n"

    # Policies formatting
    policies_text = ""
    if context.policies:
        for p in context.policies:
            rule_summary = json.dumps(p.get("rule", {})) if p.get("rule") else "N/A"
            policies_text += f"- [{p.get('policy_type')}] {p.get('title')}: {p.get('description') or ''} (Rules: {rule_summary})\n"
    else:
        policies_text = "None recorded.\n"

    # Documents formatting
    docs_text = ""
    if context.document_chunks:
        for c in context.document_chunks:
            docs_text += (
                f"\n[DOC-{c.document_id}] (Title: \"{c.document_title}\", Chunk #{c.chunk_index}):\n"
                f"{c.content}\n"
            )
    else:
        docs_text = "No relevant document chunks retrieved.\n"

    # Memory formatting
    mems_text = ""
    if context.memory_entries:
        for m in context.memory_entries:
            detail_str = f" - {m.detail}" if m.detail else ""
            mems_text += (
                f"\n[MEM-{m.id}] ({m.memory_type.upper()}, Importance {m.importance}/5, Date: {m.occurred_at}):\n"
                f"Summary: {m.summary}{detail_str}\n"
            )
    else:
        mems_text = "No relevant memory entries retrieved.\n"

    # Phase 3 Controlled Actions context
    actions_text = ""
    if open_tasks:
        actions_text += "#### Open Tasks:\n"
        for t in open_tasks:
            actions_text += f"- [TASK-{t.get('id')}] {t.get('title')} (Priority: {t.get('priority')}, Status: {t.get('status')})\n"
    else:
        actions_text += "#### Open Tasks: None pending.\n"

    if pending_purchase_requests:
        actions_text += "\n#### Pending Purchase Requests:\n"
        for pr in pending_purchase_requests:
            actions_text += f"- [PR-{pr.get('id')}] {pr.get('description')} (Amount: {pr.get('amount')} {pr.get('currency', 'MWK')}, Status: {pr.get('status')})\n"
    else:
        actions_text += "\n#### Pending Purchase Requests: None awaiting approval.\n"

    if pending_decisions:
        actions_text += "\n#### Pending Decisions Awaiting Human Review:\n"
        for d in pending_decisions:
            actions_text += f"- [DEC-{d.get('id')}] Action: {d.get('action_type')} (Risk: {d.get('risk_level')}, Notes: {d.get('decision_notes')})\n"
    else:
        actions_text += "\n#### Pending Decisions: None awaiting review.\n"

    if unread_notifications:
        actions_text += "\n#### Unread Notifications:\n"
        for n in unread_notifications:
            actions_text += f"- [NOTIF-{n.get('id')}] {n.get('title')}: {n.get('body')}\n"
    else:
        actions_text += "\n#### Unread Notifications: None.\n"

    prompt = f"""You are the Chief Operating Officer (COO) AI Advisor for {company_name or 'the organization'}.

### OPERATING GUARDRAILS & MANDATE:
1. ADVISORY ONLY: You are strictly an advisory AI assistant. You must NEVER claim to have taken external actions, approved financial transactions, executed contracts, sent emails, or updated external systems.
2. REASONING & SYNTHESIS: Read, analyze, and reason across the provided company context, active goals, operational policies, institutional memory, and pending actionable items. Provide insightful, strategic, and practical operational advice.
3. CITATION: Ground your insights on the provided documents, memories, and records. Whenever referencing specific organizational policies, documents, or past experiences, cite them using their bracketed IDs (e.g. [DOC-xxx], [MEM-xxx], [TASK-xxx], [PR-xxx], [DEC-xxx]).

### COMPANY OVERVIEW:
- Company Name: {company_name}
- Industry: {industry}
- Mission: {mission}
- Vision: {vision}

### LATEST COMPANY STATE SNAPSHOT:
{snapshot_text}

### CURRENT ACTIVE GOALS:
{goals_text}

### ACTIVE OPERATIONAL POLICIES:
{policies_text}

### PENDING ACTIONS, TASKS & APPROVALS:
{actions_text}

### RETRIEVED KNOWLEDGE BASE (DOCUMENTS):
{docs_text}

### RETRIEVED INSTITUTIONAL MEMORY (EXPERIENCES & LESSONS):
{mems_text}
"""
    return prompt


class BrainService:
    def __init__(self, db: Client):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.retrieval_service = RetrievalService(db)
        self.llm_service = get_llm_service()

    async def execute_chat(
        self,
        auth: AuthContext,
        message: str,
        conversation_id: Optional[UUID] = None,
        employee_id: Optional[UUID] = None,
    ) -> ChatResponse:
        company_id = auth.company_id
        resolved_employee_id = employee_id or auth.user_id
        cid_str = str(company_id)

        # 1. Resolve Calling Employee to determine permission scope
        emp_res = None
        if resolved_employee_id:
            emp_res = (
                self.db.table("employees")
                .select("id, role")
                .eq("company_id", cid_str)
                .or_(f"id.eq.{resolved_employee_id},auth_user_id.eq.{resolved_employee_id}")
                .execute()
            )
        emp_role = emp_res.data[0]["role"] if (emp_res and emp_res.data) else "owner"
        is_executive = emp_role in ["owner", "executive"]

        # 2. Resolve or Create Conversation
        conv_title = message[:60].strip() + ("..." if len(message) > 60 else "")
        if conversation_id:
            conv_res = (
                self.db.table("coo_conversations")
                .select("id, title")
                .eq("id", str(conversation_id))
                .eq("company_id", cid_str)
                .execute()
            )
            if not conv_res.data:
                new_conv = {
                    "id": str(conversation_id),
                    "company_id": cid_str,
                    "employee_id": str(resolved_employee_id) if resolved_employee_id else None,
                    "title": conv_title,
                }
                self.db.table("coo_conversations").insert(new_conv).execute()
        else:
            new_conv = {
                "company_id": cid_str,
                "employee_id": str(resolved_employee_id) if resolved_employee_id else None,
                "title": conv_title,
            }
            insert_res = self.db.table("coo_conversations").insert(new_conv).execute()
            if insert_res.data:
                conversation_id = UUID(insert_res.data[0]["id"])
            else:
                conversation_id = uuid.uuid4()

        # 3. Save User Message
        user_msg_data = {
            "conversation_id": str(conversation_id),
            "company_id": cid_str,
            "role": "user",
            "content": message,
            "cited_document_ids": [],
            "cited_memory_ids": [],
        }
        self.db.table("coo_messages").insert(user_msg_data).execute()

        # 4. Embed User Message
        query_embedding = await self.embedding_service.get_embedding(message)

        # 5. Vector Retrieval & Structured Context Extraction
        context = await self.retrieval_service.retrieve_context(
            company_id=company_id,
            query_embedding=query_embedding,
        )

        company_name = context.company.get("name", "The Company")

        # 5b. Fetch Latest Company State Snapshot
        from app.services.company_state import CompanyStateService
        state_service = CompanyStateService(self.db)
        latest_snapshot = await state_service.get_latest_snapshot(company_id)

        # 5c. Fetch Phase 3 Operational Items (Tasks, PRs, Pending Decisions, Notifications)
        task_query = self.db.table("tasks").select("*").eq("company_id", cid_str).in_("status", ["pending", "in_progress", "blocked"])
        if not is_executive and resolved_employee_id:
            task_query = task_query.eq("assigned_to", str(resolved_employee_id))
        tasks_res = task_query.limit(8).execute()
        open_tasks = tasks_res.data or []

        pr_res = (
            self.db.table("purchase_requests")
            .select("*")
            .eq("company_id", cid_str)
            .in_("status", ["draft", "pending_approval"])
            .limit(8)
            .execute()
        )
        pending_prs = pr_res.data or []

        dec_res = (
            self.db.table("decisions")
            .select("*")
            .eq("company_id", cid_str)
            .eq("status", "pending_human")
            .limit(8)
            .execute()
        )
        pending_decisions = dec_res.data or []

        notif_query = self.db.table("notifications").select("*").eq("company_id", cid_str).neq("status", "read")
        if not is_executive and resolved_employee_id:
            notif_query = notif_query.eq("recipient_id", str(resolved_employee_id))
        notifs_res = notif_query.limit(8).execute()
        unread_notifs = notifs_res.data or []

        # 6. Fetch Conversation History
        history_res = (
            self.db.table("coo_messages")
            .select("role, content")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=False)
            .limit(10)
            .execute()
        )

        chat_messages: List[Dict[str, str]] = []

        # System Prompt with Enriched Context & Advisory Guardrails
        system_prompt = format_system_prompt(
            company_name=company_name,
            context=context,
            latest_snapshot=latest_snapshot,
            open_tasks=open_tasks,
            pending_purchase_requests=pending_prs,
            pending_decisions=pending_decisions,
            unread_notifications=unread_notifs,
        )
        chat_messages.append({"role": "system", "content": system_prompt})

        if history_res.data:
            for m in history_res.data:
                chat_messages.append({
                    "role": m["role"],
                    "content": m["content"],
                })
        else:
            chat_messages.append({"role": "user", "content": message})

        # 7. Call LLM Service
        reply = await self.llm_service.chat(chat_messages)

        # 8. Determine Citations from retrieved documents & memories
        unique_doc_ids: List[UUID] = []
        for chunk in context.document_chunks:
            if chunk.document_id not in unique_doc_ids:
                unique_doc_ids.append(chunk.document_id)

        unique_mem_ids: List[UUID] = []
        for mem in context.memory_entries:
            if mem.id not in unique_mem_ids:
                unique_mem_ids.append(mem.id)

        # 9. Save Assistant Message with Citations
        asst_msg_data = {
            "conversation_id": str(conversation_id),
            "company_id": cid_str,
            "role": "assistant",
            "content": reply,
            "cited_document_ids": [str(d) for d in unique_doc_ids],
            "cited_memory_ids": [str(m) for m in unique_mem_ids],
        }

        saved_asst_res = self.db.table("coo_messages").insert(asst_msg_data).execute()
        asst_msg_id = (
            UUID(saved_asst_res.data[0]["id"])
            if saved_asst_res.data
            else uuid.uuid4()
        )

        return ChatResponse(
            conversation_id=conversation_id,
            message_id=asst_msg_id,
            reply=reply,
            cited_document_ids=unique_doc_ids,
            cited_memory_ids=unique_mem_ids,
            retrieved_documents_count=len(context.document_chunks),
            retrieved_memories_count=len(context.memory_entries),
        )
