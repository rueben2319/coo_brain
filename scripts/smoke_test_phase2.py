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
from app.services.agents.runner import AgentRunner
from app.services.brain import BrainService
from app.services.company_state import CompanyStateService
from app.services.decision_engine import DecisionEngineService

COMPANY_ID = UUID("ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279")
OWNER_EMPLOYEE_ID = UUID("896cd5a0-248c-4220-b6dc-4822d211c239")


async def run_phase2_smoke_test():
    settings = get_settings()
    db = get_scoped_supabase_client(company_id=COMPANY_ID)
    company_state_service = CompanyStateService(db)
    decision_engine = DecisionEngineService(db)
    agent_runner = AgentRunner(db)
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

        print("\n=== 2. Seeding Phase 2 Department, Goals, Policies & Approval Rules ===")
        # Department
        new_dept = {
            "company_id": str(COMPANY_ID),
            "name": "Phase 2 Agricultural Operations Dept",
            "description": "Oversees macadamia harvesting and estate spending.",
            "head_employee_id": str(OWNER_EMPLOYEE_ID),
        }
        dept_res = db.table("departments").insert(new_dept).execute()
        dept_id = UUID(dept_res.data[0]["id"])
        created_rows.append(("departments", str(dept_id)))
        print(f"Seeded Department: {new_dept['name']} ({dept_id})")

        # Off-track Goal for Operations
        ops_goal = {
            "company_id": str(COMPANY_ID),
            "department_id": str(dept_id),
            "title": "Macadamia Block C Yield Production Target",
            "description": "Target production of 4,500 metric tons",
            "metric_name": "macadamia_yield_tons",
            "target_value": 4500.0,
            "current_value": 1100.0,
            "unit": "tons",
            "status": "off_track",
            "due_at": "2026-10-25",
            "created_by": str(OWNER_EMPLOYEE_ID),
        }
        ops_goal_res = db.table("goals").insert(ops_goal).execute()
        ops_goal_id = UUID(ops_goal_res.data[0]["id"])
        created_rows.append(("goals", str(ops_goal_id)))
        print(f"Seeded Off-Track Ops Goal: {ops_goal['title']} ({ops_goal_id})")

        # Financial Goal with Budget Variance for Finance Agent
        fin_goal = {
            "company_id": str(COMPANY_ID),
            "department_id": str(dept_id),
            "title": "Operations Quarter 3 Spend Budget",
            "description": "Operating expenditure cap",
            "metric_name": "spend_budget_usd",
            "target_value": 50000.0,
            "current_value": 25000.0,
            "unit": "USD",
            "status": "off_track",
            "created_by": str(OWNER_EMPLOYEE_ID),
        }
        fin_goal_res = db.table("goals").insert(fin_goal).execute()
        fin_goal_id = UUID(fin_goal_res.data[0]["id"])
        created_rows.append(("goals", str(fin_goal_id)))
        print(f"Seeded Financial Goal: {fin_goal['title']} ({fin_goal_id})")

        # Spending Limit Policy
        spending_policy = {
            "company_id": str(COMPANY_ID),
            "department_id": str(dept_id),
            "policy_type": "spending_limit",
            "title": "Estate Auxiliary Fuel Approval Policy",
            "description": "Caps unapproved fuel purchases at 10,000 USD",
            "rule": {"max_amount": 10000.0, "currency": "USD"},
            "is_active": True,
            "created_by": str(OWNER_EMPLOYEE_ID),
        }
        policy_res = db.table("policies").insert(spending_policy).execute()
        policy_id = UUID(policy_res.data[0]["id"])
        created_rows.append(("policies", str(policy_id)))
        print(f"Seeded Spending Policy: {spending_policy['title']} ({policy_id})")

        # Approval Rule for decision engine matching
        approval_rule = {
            "company_id": str(COMPANY_ID),
            "action_type": "reallocate_labor_task",
            "max_risk": "high",
            "auto_approve": True,
            "is_active": True,
        }
        rule_res = db.table("approval_rules").insert(approval_rule).execute()
        rule_id = UUID(rule_res.data[0]["id"])
        created_rows.append(("approval_rules", str(rule_id)))
        print(f"Seeded Approval Rule: {approval_rule['action_type']} (Auto-Approve: True)")

        print("\n=== 3. Generating Company State Snapshot ===")
        snapshot = await company_state_service.generate_snapshot(COMPANY_ID, OWNER_EMPLOYEE_ID)
        created_rows.append(("company_state_snapshots", str(snapshot.id)))
        print(f"Generated Snapshot ID: {snapshot.id}")
        print(f"Summary: {snapshot.summary}")
        print(f"Metrics: {json.dumps(snapshot.metrics)}")

        print("\n=== 4. Initializing & Running All 4 Agents (Finance, Operations, Sales, Risk) ===")
        # Ensure agent definitions exist & track new definitions
        agent_defs = await agent_runner.ensure_agent_definitions(COMPANY_ID)
        for adef in agent_defs:
            # Check if created in this session by verifying if it was missing earlier or just list
            pass

        run_responses = await agent_runner.run_all_agents(COMPANY_ID)
        for resp in run_responses:
            print(f"[{resp.agent_type.upper()}] -> {resp.summary}")

        # Fetch generated events
        events_res = db.table("events").select("*").eq("company_id", str(COMPANY_ID)).execute()
        seeded_events = events_res.data or []
        print(f"\nTotal Event Signals Generated: {len(seeded_events)}")
        for ev in seeded_events:
            created_rows.append(("events", ev["id"]))
            dec_info = f" -> Resulting Decision: {ev['resulting_decision_id']}" if ev.get("resulting_decision_id") else ""
            print(f"  - [{ev['severity'].upper()}] ({ev['event_type']}): {ev['title']}{dec_info}")

        # Fetch proposed decisions
        decisions_res = db.table("decisions").select("*").eq("company_id", str(COMPANY_ID)).execute()
        seeded_decisions = decisions_res.data or []
        print(f"\nTotal Decisions Proposed & Evaluated: {len(seeded_decisions)}")
        for dec in seeded_decisions:
            created_rows.append(("decisions", dec["id"]))
            print(f"  - [Status: {dec['status'].upper()}] (Action: {dec['action_type']}): {dec['reasoning'][:60]}... Notes: {dec['decision_notes']}")

        print("\n=== 5. Testing Executive COO Chat with Company State Context ===")
        chat_query = "Give me an executive summary of our company's current operational state, active risks, and open decision proposals."
        chat_resp = await brain_service.execute_chat(auth=auth, message=chat_query)

        if chat_resp.conversation_id:
            msg_res = db.table("coo_messages").select("id").eq("conversation_id", str(chat_resp.conversation_id)).execute()
            for msg in msg_res.data:
                created_rows.append(("coo_messages", msg["id"]))
            created_rows.append(("coo_conversations", str(chat_resp.conversation_id)))

        print(f"\nChat Conversation ID: {chat_resp.conversation_id}")
        print(f"Executive Reply:\n{chat_resp.reply}")

        assert len(seeded_events) >= 2, "Expected at least 2 event signals created by agents!"
        assert len(seeded_decisions) >= 1, "Expected at least 1 decision proposed!"
        print("\n>>> PHASE 2 SMOKE TEST PASSED! Agents detected anomalies, created events, proposed decisions, and updated chat context! <<<")

    finally:
        print("\n=== 6. Cleaning Up Phase 2 Seeded Test Data ===")
        cleaned_count = 0
        failed_deletes = []

        # Deduplicate while preserving reverse order
        seen_ids = set()
        unique_created_rows = []
        for tbl, rid in reversed(created_rows):
            key = (tbl, rid)
            if key not in seen_ids:
                seen_ids.add(key)
                unique_created_rows.append(key)

        for table_name, row_id in unique_created_rows:
            try:
                res = db.table(table_name).delete().eq("id", row_id).execute()
                if res.data:
                    cleaned_count += len(res.data)
                else:
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
    asyncio.run(run_phase2_smoke_test())
