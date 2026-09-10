import asyncio
import json
import os
import sys
import uuid
from typing import List, Tuple
from uuid import UUID

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.auth import AuthContext
from app.config import get_settings
from app.database import get_scoped_supabase_client
from app.services.brain import BrainService
from app.services.chunking import chunk_text
from app.services.embedding import get_embedding_service

COMPANY_ID = UUID("ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279")
OWNER_EMPLOYEE_ID = UUID("896cd5a0-248c-4220-b6dc-4822d211c239")


async def run_smoke_test():
    settings = get_settings()
    db = get_scoped_supabase_client(company_id=COMPANY_ID)
    embedding_service = get_embedding_service()
    brain_service = BrainService(db)

    auth = AuthContext(
        company_id=COMPANY_ID,
        user_id=OWNER_EMPLOYEE_ID,
        email="ruebenisaac1@gmail.com",
        role="owner",
    )

    created_rows: List[Tuple[str, str]] = []

    try:
        print("=== 1. Checking Existing Seed Company & Owner Employee ===")
        comp_res = db.table("companies").select("*").eq("id", str(COMPANY_ID)).execute()
        print(f"Company: {comp_res.data[0]['name']} (ID: {COMPANY_ID})")

        emp_res = db.table("employees").select("*").eq("id", str(OWNER_EMPLOYEE_ID)).execute()
        print(f"Employee: {emp_res.data[0]['full_name']} (Role: {emp_res.data[0]['role']})")

        print("\n=== 2. Seeding Department ===")
        dept_res = db.table("departments").select("*").eq("company_id", str(COMPANY_ID)).execute()
        dept_id = None
        if dept_res.data:
            dept_id = UUID(dept_res.data[0]["id"])
            print(f"Using existing department: {dept_res.data[0]['name']} ({dept_id})")
        else:
            new_dept = {
                "company_id": str(COMPANY_ID),
                "name": "Agriculture & Estate Operations",
                "description": "Oversees macadamia, tea, and coffee plantations, irrigation, and processing plants.",
                "head_employee_id": str(OWNER_EMPLOYEE_ID),
            }
            res = db.table("departments").insert(new_dept).execute()
            dept_id = UUID(res.data[0]["id"])
            created_rows.append(("departments", str(dept_id)))
            print(f"Created department: {new_dept['name']} ({dept_id})")

        print("\n=== 3. Seeding Goal ===")
        goal_res = db.table("goals").select("*").eq("company_id", str(COMPANY_ID)).execute()
        goal_id = None
        if goal_res.data:
            goal_id = UUID(goal_res.data[0]["id"])
            print(f"Using existing goal: {goal_res.data[0]['title']} ({goal_id})")
        else:
            new_goal = {
                "company_id": str(COMPANY_ID),
                "department_id": str(dept_id),
                "title": "Achieve 4,500 Metric Tons Macadamia Production",
                "description": "Increase harvest yield while maintaining export-grade kernel recovery above 33%.",
                "metric_name": "macadamia_yield_tons",
                "target_value": 4500.0,
                "current_value": 1250.0,
                "unit": "tons",
                "status": "on_track",
                "starts_at": "2026-01-01",
                "due_at": "2026-12-31",
                "created_by": str(OWNER_EMPLOYEE_ID),
            }
            res = db.table("goals").insert(new_goal).execute()
            goal_id = UUID(res.data[0]["id"])
            created_rows.append(("goals", str(goal_id)))
            print(f"Created goal: {new_goal['title']} ({goal_id})")

        print("\n=== 4. Seeding Policy ===")
        policy_res = db.table("policies").select("*").eq("company_id", str(COMPANY_ID)).execute()
        policy_id = None
        if policy_res.data:
            policy_id = UUID(policy_res.data[0]["id"])
            print(f"Using existing policy: {policy_res.data[0]['title']} ({policy_id})")
        else:
            new_policy = {
                "company_id": str(COMPANY_ID),
                "department_id": str(dept_id),
                "policy_type": "sop",
                "title": "Dry Season Borehole and Irrigation Operating SOP",
                "description": "Regulates water pump run hours and transformer loads during dry months.",
                "rule": {"max_daily_pumping_hours": 6, "allowed_window": "05:00-11:00", "generator_approval_required": True},
                "is_active": True,
                "created_by": str(OWNER_EMPLOYEE_ID),
            }
            res = db.table("policies").insert(new_policy).execute()
            policy_id = UUID(res.data[0]["id"])
            created_rows.append(("policies", str(policy_id)))
            print(f"Created policy: {new_policy['title']} ({policy_id})")

        print("\n=== 5. Ingesting Document with Chunks & Embeddings ===")
        sop_title = "SOP-2026: Irrigation and Borehole Energy Management"
        doc_text = (
            "Standard Operating Procedure: Irrigation Protocols and Borehole Energy Allocation for Sable Farming.\n\n"
            "1. Borehole Pumping Windows: During peak dry season (September through November), borehole pumps "
            "must operate strictly between 05:00 and 11:00. Pumping outside this window causes transformer overheating "
            "and electrical surcharge penalties.\n\n"
            "2. Soil Moisture Thresholds: Tensiometer readings must be logged twice daily. Water application is suspended "
            "if root zone moisture exceeds 75 centibars.\n\n"
            "3. Emergency Generator Fuel: Any diesel fuel requisition exceeding 500 liters for auxiliary pump generators "
            "requires authorization from the Operations Head."
        )

        doc_res = (
            db.table("documents")
            .select("*")
            .eq("company_id", str(COMPANY_ID))
            .eq("title", sop_title)
            .execute()
        )
        doc_id = None
        if doc_res.data:
            doc_id = UUID(doc_res.data[0]["id"])
            print(f"Using existing SOP document: {sop_title} ({doc_id})")
        else:
            new_doc = {
                "company_id": str(COMPANY_ID),
                "department_id": str(dept_id),
                "title": sop_title,
                "doc_type": "sop",
                "raw_text": doc_text,
                "uploaded_by": str(OWNER_EMPLOYEE_ID),
            }
            doc_insert = db.table("documents").insert(new_doc).execute()
            doc_id = UUID(doc_insert.data[0]["id"])
            created_rows.append(("documents", str(doc_id)))
            print(f"Created document: {new_doc['title']} ({doc_id})")

        # Ensure chunks exist for doc_id
        chunks_check = (
            db.table("document_chunks")
            .select("id")
            .eq("document_id", str(doc_id))
            .execute()
        )
        if not chunks_check.data:
            chunks = chunk_text(doc_text)
            embeddings = await embedding_service.get_embeddings(chunks)
            chunk_rows = [
                {
                    "document_id": str(doc_id),
                    "company_id": str(COMPANY_ID),
                    "chunk_index": idx,
                    "content": c,
                    "embedding": emb,
                }
                for idx, (c, emb) in enumerate(zip(chunks, embeddings))
            ]
            chunks_insert = db.table("document_chunks").insert(chunk_rows).execute()
            for chunk_data in chunks_insert.data:
                created_rows.append(("document_chunks", chunk_data["id"]))
            print(f"Ingested and embedded {len(chunks_insert.data)} chunks into document_chunks table.")
        else:
            print(f"Document already has {len(chunks_check.data)} chunks.")

        print("\n=== 6. Recording Institutional Memory with Auto-Embedding ===")
        mem_res = db.table("memory_entries").select("*").eq("company_id", str(COMPANY_ID)).execute()
        mem_id = None
        if mem_res.data:
            mem_id = UUID(mem_res.data[0]["id"])
            print(f"Using existing memory entry: {mem_res.data[0]['summary']} ({mem_id})")
        else:
            summary_text = "Delayed macadamia nut harvesting past October 25 caused 15% moisture decay in Block C"
            detail_text = (
                "During the 2025 harvest, delayed transit to drying sheds coincided with unseasonal early rains. "
                "Kernel recovery dropped by 4.2% and moisture damage resulted in export price deductions. "
                "Harvest teams must conclude field collection before October 25 regardless of crop moisture."
            )
            mem_embedding = await embedding_service.get_embedding(summary_text)

            new_mem = {
                "company_id": str(COMPANY_ID),
                "related_department_id": str(dept_id),
                "related_goal_id": str(goal_id),
                "memory_type": "lesson",
                "summary": summary_text,
                "detail": detail_text,
                "importance": 5,
                "embedding": mem_embedding,
            }
            mem_insert = db.table("memory_entries").insert(new_mem).execute()
            mem_id = UUID(mem_insert.data[0]["id"])
            created_rows.append(("memory_entries", str(mem_id)))
            print(f"Recorded memory entry: {summary_text[:50]}... ({mem_id})")

        print("\n=== 7. Executing Live Smoke Test: POST /coo/chat ===")
        user_query = (
            "What are our operating rules for borehole pumping during the dry season, "
            "and what lessons do we have regarding harvest timing for macadamia?"
        )
        print(f"User Query: \"{user_query}\"")

        response = await brain_service.execute_chat(
            auth=auth,
            message=user_query,
        )

        # Track conversation and messages created during execute_chat
        if response.conversation_id:
            msg_res = (
                db.table("coo_messages")
                .select("id")
                .eq("conversation_id", str(response.conversation_id))
                .execute()
            )
            for msg_row in msg_res.data:
                created_rows.append(("coo_messages", msg_row["id"]))
            created_rows.append(("coo_conversations", str(response.conversation_id)))

        print("\n=== 8. Chat Response & Citation Verification ===")
        print(f"Conversation ID: {response.conversation_id}")
        print(f"Message ID: {response.message_id}")
        print(f"Retrieved Document Chunks: {response.retrieved_documents_count}")
        print(f"Retrieved Memory Entries: {response.retrieved_memories_count}")
        print(f"Cited Document IDs: {response.cited_document_ids}")
        print(f"Cited Memory IDs: {response.cited_memory_ids}")
        print(f"\nExecutive Reply:\n{response.reply}")

        # Assertions
        assert len(response.cited_document_ids) > 0, "Expected at least 1 cited document ID!"
        assert len(response.cited_memory_ids) > 0, "Expected at least 1 cited memory ID!"
        print("\n>>> SMOKE TEST PASSED! The COO chat endpoint retrieved and cited real documents and memories! <<<")

    finally:
        print("\n=== 9. Cleaning Up Seeded Test Data ===")
        cleaned_count = 0
        failed_deletes = []

        for table_name, row_id in reversed(created_rows):
            try:
                res = db.table(table_name).delete().eq("id", row_id).execute()
                if res.data:
                    cleaned_count += len(res.data)
                else:
                    # Check if already deleted or cascade-deleted
                    check_res = db.table(table_name).select("id").eq("id", row_id).execute()
                    if not check_res.data:
                        print(f"Row {row_id} in {table_name} already deleted (e.g. via cascade).")
                    else:
                        print(f"WARNING: Delete executed for {table_name} id {row_id} but row still exists.")
                        failed_deletes.append((table_name, row_id, "Row still present after delete"))
            except Exception as e:
                print(f"ERROR: Failed to delete {table_name} with id {row_id}: {e}")
                failed_deletes.append((table_name, row_id, str(e)))

        if failed_deletes:
            print(f"\nCRITICAL: {len(failed_deletes)} rows failed to delete:")
            for t_name, r_id, err in failed_deletes:
                print(f"  - Table: {t_name}, ID: {r_id}, Error: {err}")

        print(f"\nCleaned up {cleaned_count} seeded rows from ai-coo (live).")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
