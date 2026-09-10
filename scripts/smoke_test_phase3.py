import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Ensure app is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from app.database import get_scoped_supabase_client
from app.services.decision_engine import DecisionEngineService, ROLE_HIERARCHY
from app.models.decision import DecisionStatus, RiskLevel
from app.models.task import TaskPriority, TaskStatus
from app.models.notification import NotificationChannel, NotificationStatus
from app.models.purchase_request import PurchaseRequestStatus
from app.models.report import ReportType, ReportGenerateRequest
from app.services.report_generator import ReportGeneratorService
from app.services.brain import BrainService
from app.auth import AuthContext

COMPANY_ID = uuid.UUID("ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279")


async def run_smoke_test_phase3():
    db = get_scoped_supabase_client(company_id=COMPANY_ID)
    created_rows = []

    print("\n=======================================================")
    print("      AI COO — Phase 3 Controlled Actions Smoke Test    ")
    print("=======================================================\n")

    try:
        # 1. Fetch Existing Company & Owner Employee
        print("=== 1. Checking Existing Company & Owner Employee ===")
        comp_res = db.table("companies").select("*").eq("id", str(COMPANY_ID)).execute()
        if not comp_res.data:
            print(f"ERROR: Company {COMPANY_ID} not found.")
            sys.exit(1)
        company = comp_res.data[0]
        company_id = uuid.UUID(company["id"])
        print(f"Company: {company['name']} (ID: {company_id})")

        owner_res = (
            db.table("employees")
            .select("*")
            .eq("company_id", str(company_id))
            .eq("role", "owner")
            .limit(1)
            .execute()
        )
        if not owner_res.data:
            print("ERROR: No owner employee found.")
            sys.exit(1)
        owner_emp = owner_res.data[0]
        owner_emp_id = uuid.UUID(owner_emp["id"])
        print(f"Owner Employee: {owner_emp['full_name']} (ID: {owner_emp_id}, Role: {owner_emp['role']})")

        # 2. Seed Phase 3 Test Department, Goal, Policy & Approval Rules
        print("\n=== 2. Seeding Phase 3 Test Infrastructure ===")
        dept_data = {
            "company_id": str(company_id),
            "name": "Phase 3 Agronomy & Operations Dept",
            "description": "Department for Phase 3 controlled action testing",
        }
        dept_row = db.table("departments").insert(dept_data).execute().data[0]
        created_rows.append(("departments", dept_row["id"]))
        dept_id = uuid.UUID(dept_row["id"])
        print(f"Seeded Department: {dept_row['name']} ({dept_id})")

        # Seed Staff Employee (for role authorization testing)
        staff_data = {
            "company_id": str(company_id),
            "department_id": str(dept_id),
            "full_name": "Test Field Worker",
            "email": f"worker_{uuid.uuid4().hex[:6]}@example.com",
            "role": "staff",
            "title": "Junior Field Assistant",
            "is_active": True,
        }
        staff_row = db.table("employees").insert(staff_data).execute().data[0]
        created_rows.append(("employees", staff_row["id"]))
        staff_emp_id = uuid.UUID(staff_row["id"])
        print(f"Seeded Staff Employee (Underprivileged): {staff_row['full_name']} ({staff_emp_id}, Role: staff)")

        # Seed Goal
        goal_data = {
            "company_id": str(company_id),
            "department_id": str(dept_id),
            "title": "Phase 3 Irrigation Pump Overhaul",
            "description": "Critical overhaul of estate irrigation pumps",
            "metric_name": "pump_completion_pct",
            "target_value": 100.0,
            "current_value": 30.0,
            "unit": "percent",
            "status": "off_track",
            "created_by": str(owner_emp_id),
        }
        goal_row = db.table("goals").insert(goal_data).execute().data[0]
        created_rows.append(("goals", goal_row["id"]))
        goal_id = uuid.UUID(goal_row["id"])
        print(f"Seeded Goal: {goal_row['title']} ({goal_id})")

        # Seed Policy
        policy_data = {
            "company_id": str(company_id),
            "department_id": str(dept_id),
            "title": "Emergency Equipment Maintenance SOP",
            "policy_type": "sop",
            "description": "SOP for urgent equipment repair and labor reallocation",
            "rule": {"max_spending": 20000},
            "is_active": True,
        }
        policy_row = db.table("policies").insert(policy_data).execute().data[0]
        created_rows.append(("policies", policy_row["id"]))
        print(f"Seeded Policy: {policy_row['title']}")

        # Seed Approval Rule (requires 'manager')
        appr_rule_data = {
            "company_id": str(company_id),
            "action_type": "budget_review_task",
            "max_risk": "high",
            "required_approver_role": "manager",
            "auto_approve": False,
            "is_active": True,
        }
        rule_row = db.table("approval_rules").insert(appr_rule_data).execute().data[0]
        created_rows.append(("approval_rules", rule_row["id"]))
        print(f"Seeded Approval Rule: {rule_row['action_type']} (Req Role: manager, Auto-Approve: False)")

        # 3. Propose Decision (landing at pending_human)
        print("\n=== 3. Testing Decision Proposal & Role-Enforced Approval ===")
        engine = DecisionEngineService(db)
        decision = await engine.propose_decision(
            company_id=company_id,
            proposed_by=owner_emp_id,
            action_type="budget_review_task",
            action_payload={"budget_name": "Irrigation Overhaul Budget", "metric_name": "Maintenance Variance"},
            reasoning="Irrigation project is lagging due to budget constraint.",
            risk_level=RiskLevel.HIGH,
            department_id=dept_id,
            related_goal_id=goal_id,
        )

        created_rows.append(("decisions", str(decision.id)))
        print(f"Proposed Decision: {decision.id} (Status: {decision.status})")
        assert decision.status == DecisionStatus.PENDING_HUMAN, f"Expected pending_human, got {decision.status}"

        # 3b. Test Unauthorized Approval Attempt by Staff
        print("\n--- Testing Role Hierarchy Enforcement ---")
        unauth_failed_as_expected = False
        try:
            await engine.approve_decision(
                decision_id=decision.id,
                company_id=company_id,
                approver_user_id=staff_emp_id,
                notes="Staff worker attempting approval",
            )
        except PermissionError as pe:
            unauth_failed_as_expected = True
            print(f"[PASS] Correctly Blocked Staff Approval: {pe}")

        assert unauth_failed_as_expected, "CRITICAL: Staff role was able to bypass approval hierarchy!"

        # 3c. Authorized Approval by Owner
        approved_decision = await engine.approve_decision(
            decision_id=decision.id,
            company_id=company_id,
            approver_user_id=owner_emp_id,
            notes="Approved by Executive Owner for urgent irrigation turnaround.",
        )
        print(f"[PASS] Approved by Owner: Decision {approved_decision.id} Status: {approved_decision.status} (Decided By: {approved_decision.decided_by})")
        assert approved_decision.status == DecisionStatus.APPROVED

        # 4. Execute Decision & Verify Task + Institutional Memory Creation
        print("\n=== 4. Testing Decision Execution & Memory Creation ===")
        executed_decision = await engine.execute_decision(
            decision_id=decision.id,
            company_id=company_id,
        )
        print(f"Executed Decision {executed_decision.id}: Status={executed_decision.status}, Outcome={executed_decision.outcome}")
        assert executed_decision.status == DecisionStatus.EXECUTED

        # Verify Created Task
        tasks_res = db.table("tasks").select("*").eq("related_decision_id", str(decision.id)).execute()
        assert tasks_res.data, "Expected a task to be created from decision execution"
        created_task = tasks_res.data[0]
        created_rows.append(("tasks", created_task["id"]))
        print(f"[PASS] Verified Created Task: {created_task['title']} (ID: {created_task['id']}, Priority: {created_task['priority']})")

        # Verify Created Memory Entry
        mem_res = db.table("memory_entries").select("*").eq("company_id", str(company_id)).eq("memory_type", "decision").order("created_at", desc=True).limit(1).execute()
        assert mem_res.data, "Expected a memory_entries row to be created on decision execution"
        created_mem = mem_res.data[0]
        created_rows.append(("memory_entries", created_mem["id"]))
        print(f"[PASS] Verified Institutional Memory: {created_mem['summary']} (ID: {created_mem['id']})")

        # 5. Testing Independent Purchase Request Workflow
        print("\n=== 5. Testing Isolated Purchase Request Workflow ===")
        pr_data = {
            "company_id": str(company_id),
            "department_id": str(dept_id),
            "requested_by": str(owner_emp_id),
            "vendor": "Lilongwe Hydraulics Ltd",
            "description": "High-capacity submersible water pump for Block C",
            "amount": 75000.0,
            "currency": "MWK",
            "status": "pending_approval",
        }
        pr_row = db.table("purchase_requests").insert(pr_data).execute().data[0]
        created_rows.append(("purchase_requests", pr_row["id"]))
        pr_id = uuid.UUID(pr_row["id"])
        print(f"Created Purchase Request: {pr_row['description']} ({pr_id}, Amount: {pr_row['amount']} {pr_row['currency']})")

        # Approve Purchase Request
        upd_pr = db.table("purchase_requests").update({
            "status": "approved",
            "approved_by": str(owner_emp_id),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Approved for critical estate infrastructure",
        }).eq("id", str(pr_id)).execute().data[0]
        print(f"[PASS] Approved Purchase Request: Status={upd_pr['status']}, Approved By={upd_pr['approved_by']}")
        assert upd_pr["status"] == "approved"

        # 6. Generate Report
        print("\n=== 6. Testing Operational Report Generation ===")
        rep_gen = ReportGeneratorService(db)
        report = await rep_gen.generate_report(
            company_id=company_id,
            request=ReportGenerateRequest(
                report_type=ReportType.WEEKLY_SUMMARY,
                title="Phase 3 Verification Weekly Report",
            ),
            generated_by=owner_emp_id,
        )
        created_rows.append(("reports", str(report.id)))
        print(f"[PASS] Generated Report: {report.title} (ID: {report.id}, Length: {len(report.content)} chars)")

        # 7. Test COO Chat with Enriched Phase 3 Context
        print("\n=== 7. Testing COO Chat with Tasks & Approvals Context ===")
        auth = AuthContext(
            company_id=company_id,
            user_id=owner_emp_id,
            role="owner",
        )
        brain = BrainService(db)
        chat_resp = await brain.execute_chat(
            auth=auth,
            message="What active operational tasks, purchase requests, and decisions are currently tracked in the system?",
        )
        created_rows.append(("coo_conversations", str(chat_resp.conversation_id)))
        print(f"Conversation ID: {chat_resp.conversation_id}")
        print("\nCOO Reply Excerpt:")
        print(chat_resp.reply[:600] + "...\n")

        print(">>> ALL PHASE 3 VERIFICATIONS PASSED! <<<")

    finally:
        print("\n=== 8. Cleaning Up Phase 3 Seeded Test Data ===")
        cleaned_count = 0
        for table, row_id in reversed(created_rows):
            try:
                del_res = db.table(table).delete().eq("id", str(row_id)).execute()
                if del_res.data:
                    cleaned_count += len(del_res.data)
                else:
                    print(f"Row {row_id} in {table} already deleted (e.g. via cascade).")
            except Exception as e:
                print(f"Error deleting {row_id} from {table}: {e}")

        print(f"\nCleaned up {cleaned_count} seeded rows from ai-coo (live).\n")


if __name__ == "__main__":
    asyncio.run(run_smoke_test_phase3())
