from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID
from supabase import Client

from app.models.decision import DecisionCreate, DecisionRead, DecisionStatus, RiskLevel
from app.models.notification import NotificationChannel, NotificationStatus
from app.models.task import TaskPriority, TaskStatus

logger = logging.getLogger("coo_brain.decision_engine")

ROLE_HIERARCHY = {
    "staff": 1,
    "manager": 2,
    "executive": 3,
    "owner": 4,
    "ai_agent": 0,
}


class DecisionEngineService:
    def __init__(self, db: Client):
        self.db = db

    def _resolve_employee(self, company_id: UUID, employee_or_user_id: UUID) -> Optional[Dict[str, Any]]:
        cid_str = str(company_id)
        uid_str = str(employee_or_user_id)
        # Try direct employee ID match
        emp_res = (
            self.db.table("employees")
            .select("*")
            .eq("company_id", cid_str)
            .eq("id", uid_str)
            .execute()
        )
        if emp_res.data:
            return emp_res.data[0]

        # Try auth_user_id match
        emp_res = (
            self.db.table("employees")
            .select("*")
            .eq("company_id", cid_str)
            .eq("auth_user_id", uid_str)
            .execute()
        )
        if emp_res.data:
            return emp_res.data[0]

        # In dev mode, return the first owner/executive employee if exists
        emp_res = (
            self.db.table("employees")
            .select("*")
            .eq("company_id", cid_str)
            .eq("is_active", True)
            .in_("role", ["owner", "executive"])
            .limit(1)
            .execute()
        )
        if emp_res.data:
            return emp_res.data[0]

        return None

    def _resolve_target_employee(
        self,
        company_id: UUID,
        department_id: Optional[UUID] = None,
        min_role: str = "manager",
    ) -> Optional[str]:
        cid_str = str(company_id)
        if department_id:
            dept_res = (
                self.db.table("employees")
                .select("id, role")
                .eq("company_id", cid_str)
                .eq("department_id", str(department_id))
                .eq("is_active", True)
                .execute()
            )
            if dept_res.data:
                sorted_dept = sorted(
                    dept_res.data,
                    key=lambda x: ROLE_HIERARCHY.get(x.get("role", "staff"), 0),
                    reverse=True,
                )
                return sorted_dept[0]["id"]

        exec_res = (
            self.db.table("employees")
            .select("id, role")
            .eq("company_id", cid_str)
            .eq("is_active", True)
            .in_("role", ["owner", "executive"])
            .execute()
        )
        if exec_res.data:
            sorted_exec = sorted(
                exec_res.data,
                key=lambda x: ROLE_HIERARCHY.get(x.get("role", "staff"), 0),
                reverse=True,
            )
            return sorted_exec[0]["id"]

        any_res = (
            self.db.table("employees")
            .select("id")
            .eq("company_id", cid_str)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if any_res.data:
            return any_res.data[0]["id"]
        return None

    async def propose_decision(
        self,
        company_id: UUID,
        proposed_by: UUID,
        action_type: str,
        action_payload: Dict[str, Any],
        reasoning: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        department_id: Optional[UUID] = None,
        related_goal_id: Optional[UUID] = None,
    ) -> DecisionRead:
        cid_str = str(company_id)
        decision_data = {
            "company_id": cid_str,
            "proposed_by": str(proposed_by),
            "action_type": action_type,
            "action_payload": action_payload,
            "reasoning": reasoning,
            "risk_level": risk_level.value if isinstance(risk_level, RiskLevel) else risk_level,
            "department_id": str(department_id) if department_id else None,
            "related_goal_id": str(related_goal_id) if related_goal_id else None,
            "status": DecisionStatus.PROPOSED.value,
        }

        res = self.db.table("decisions").insert(decision_data).execute()
        decision_row = res.data[0]
        decision = DecisionRead(**decision_row)
        logger.info(f"Proposed new decision {decision.id} (Action: {action_type}, Risk: {risk_level})")

        # Automatically evaluate decision status against approval rules
        evaluated_decision = await self.evaluate_decision(decision.id, company_id)
        return evaluated_decision

    async def evaluate_decision(self, decision_id: UUID, company_id: UUID) -> DecisionRead:
        cid_str = str(company_id)
        dec_res = (
            self.db.table("decisions")
            .select("*")
            .eq("id", str(decision_id))
            .eq("company_id", cid_str)
            .execute()
        )
        if not dec_res.data:
            raise ValueError(f"Decision {decision_id} not found for company {company_id}")

        decision = dec_res.data[0]
        action_type = decision.get("action_type")
        risk_level = decision.get("risk_level")
        action_payload = decision.get("action_payload") or {}
        amount = action_payload.get("amount") or action_payload.get("estimated_cost")

        # Check approval_rules table for matching rule
        rules_res = (
            self.db.table("approval_rules")
            .select("*")
            .eq("company_id", cid_str)
            .eq("is_active", True)
            .eq("action_type", action_type)
            .execute()
        )

        matched_rule = None
        if rules_res.data:
            for rule in rules_res.data:
                max_amount = rule.get("max_amount")
                if max_amount is not None and amount is not None and float(amount) > float(max_amount):
                    continue

                rule_risk = rule.get("max_risk")
                risk_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
                if risk_order.get(risk_level, 2) <= risk_order.get(rule_risk, 2):
                    matched_rule = rule
                    break

        new_status = DecisionStatus.PENDING_HUMAN.value
        notes = "Pending manual executive review."

        if matched_rule:
            rule_id = matched_rule["id"]
            if matched_rule.get("auto_approve"):
                new_status = DecisionStatus.AUTO_APPROVED.value
                notes = f"Auto-approved via approval rule {rule_id} ({action_type})."
            else:
                new_status = DecisionStatus.PENDING_HUMAN.value
                notes = f"Requires approval from role: {matched_rule.get('required_approver_role')}."
        else:
            notes = f"No matching auto-approval rule for action '{action_type}' with risk '{risk_level}'. Requires approval."

        # Look up matching policy in policies table if present
        policies_res = (
            self.db.table("policies")
            .select("id")
            .eq("company_id", cid_str)
            .eq("is_active", True)
            .in_("policy_type", ["spending_limit", "approval_rule", "sop"])
            .execute()
        )
        matched_policy_id = policies_res.data[0]["id"] if policies_res.data else None

        update_data = {
            "status": new_status,
            "matched_policy_id": matched_policy_id,
            "decision_notes": notes,
        }

        upd_res = (
            self.db.table("decisions")
            .update(update_data)
            .eq("id", str(decision_id))
            .execute()
        )

        updated_row = upd_res.data[0]
        logger.info(f"Evaluated decision {decision_id}: status={new_status}, notes='{notes}'")
        return DecisionRead(**updated_row)

    def _get_required_role_for_decision(self, company_id: UUID, decision: Dict[str, Any]) -> str:
        action_type = decision.get("action_type")
        risk_level = decision.get("risk_level", "medium")

        rules_res = (
            self.db.table("approval_rules")
            .select("required_approver_role, max_risk")
            .eq("company_id", str(company_id))
            .eq("is_active", True)
            .eq("action_type", action_type)
            .execute()
        )
        if rules_res.data and rules_res.data[0].get("required_approver_role"):
            return rules_res.data[0]["required_approver_role"]

        # Default fallback based on risk level
        if risk_level in ["critical", "high"]:
            return "executive"
        return "manager"

    async def approve_decision(
        self,
        decision_id: UUID,
        company_id: UUID,
        approver_user_id: UUID,
        notes: Optional[str] = None,
    ) -> DecisionRead:
        cid_str = str(company_id)
        dec_res = (
            self.db.table("decisions")
            .select("*")
            .eq("id", str(decision_id))
            .eq("company_id", cid_str)
            .execute()
        )
        if not dec_res.data:
            raise ValueError(f"Decision {decision_id} not found for company {company_id}")

        decision = dec_res.data[0]
        current_status = decision.get("status")
        if current_status != DecisionStatus.PENDING_HUMAN.value:
            raise ValueError(
                f"Cannot approve decision with status '{current_status}'. Only '{DecisionStatus.PENDING_HUMAN.value}' decisions can be approved."
            )

        # Enforce approver role hierarchy
        approver = self._resolve_employee(company_id, approver_user_id)
        if not approver:
            raise PermissionError(f"Approver with ID {approver_user_id} not found in company employees.")

        approver_role = approver.get("role", "staff")
        required_role = self._get_required_role_for_decision(company_id, decision)

        approver_level = ROLE_HIERARCHY.get(approver_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 2)

        if approver_level < required_level:
            raise PermissionError(
                f"Employee role '{approver_role}' does not meet required approval role '{required_role}'."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        approval_notes = notes or decision.get("decision_notes") or f"Approved by {approver.get('full_name', 'Executive')}."

        update_data = {
            "status": DecisionStatus.APPROVED.value,
            "decided_by": approver["id"],
            "decided_at": now_iso,
            "decision_notes": approval_notes,
        }

        upd_res = (
            self.db.table("decisions")
            .update(update_data)
            .eq("id", str(decision_id))
            .execute()
        )
        logger.info(f"Approved decision {decision_id} by {approver['id']} ({approver_role})")
        return DecisionRead(**upd_res.data[0])

    async def reject_decision(
        self,
        decision_id: UUID,
        company_id: UUID,
        approver_user_id: UUID,
        notes: str,
    ) -> DecisionRead:
        if not notes or not notes.strip():
            raise ValueError("Rejection notes are required to document rationale.")

        cid_str = str(company_id)
        dec_res = (
            self.db.table("decisions")
            .select("*")
            .eq("id", str(decision_id))
            .eq("company_id", cid_str)
            .execute()
        )
        if not dec_res.data:
            raise ValueError(f"Decision {decision_id} not found for company {company_id}")

        decision = dec_res.data[0]
        current_status = decision.get("status")
        if current_status != DecisionStatus.PENDING_HUMAN.value:
            raise ValueError(
                f"Cannot reject decision with status '{current_status}'. Only '{DecisionStatus.PENDING_HUMAN.value}' decisions can be rejected."
            )

        # Enforce approver role hierarchy
        approver = self._resolve_employee(company_id, approver_user_id)
        if not approver:
            raise PermissionError(f"Approver with ID {approver_user_id} not found in company employees.")

        approver_role = approver.get("role", "staff")
        required_role = self._get_required_role_for_decision(company_id, decision)

        approver_level = ROLE_HIERARCHY.get(approver_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 2)

        if approver_level < required_level:
            raise PermissionError(
                f"Employee role '{approver_role}' does not meet required approval role '{required_role}'."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "status": DecisionStatus.REJECTED.value,
            "decided_by": approver["id"],
            "decided_at": now_iso,
            "decision_notes": notes.strip(),
        }

        upd_res = (
            self.db.table("decisions")
            .update(update_data)
            .eq("id", str(decision_id))
            .execute()
        )
        logger.info(f"Rejected decision {decision_id} by {approver['id']} ({approver_role})")
        return DecisionRead(**upd_res.data[0])

    async def execute_decision(self, decision_id: UUID, company_id: UUID) -> DecisionRead:
        cid_str = str(company_id)
        dec_res = (
            self.db.table("decisions")
            .select("*")
            .eq("id", str(decision_id))
            .eq("company_id", cid_str)
            .execute()
        )
        if not dec_res.data:
            raise ValueError(f"Decision {decision_id} not found for company {company_id}")

        decision = dec_res.data[0]
        current_status = decision.get("status")
        if current_status not in [DecisionStatus.AUTO_APPROVED.value, DecisionStatus.APPROVED.value]:
            raise ValueError(
                f"Cannot execute decision with status '{current_status}'. Only '{DecisionStatus.AUTO_APPROVED.value}' or '{DecisionStatus.APPROVED.value}' decisions can be executed."
            )

        action_type = decision.get("action_type")
        action_payload = decision.get("action_payload") or {}
        reasoning = decision.get("reasoning")
        dept_id = decision.get("department_id")
        goal_id = decision.get("related_goal_id")
        risk_level = decision.get("risk_level", "medium")
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            outcome = ""
            if action_type == "budget_review_task":
                target_emp = self._resolve_target_employee(company_id, department_id=dept_id, min_role="manager")
                task_data = {
                    "company_id": cid_str,
                    "title": f"Budget Review: {action_payload.get('metric_name') or action_payload.get('budget_name') or 'Operational Budget Review'}",
                    "description": reasoning or "Conduct comprehensive financial review for department budget variance.",
                    "assigned_to": target_emp,
                    "department_id": str(dept_id) if dept_id else None,
                    "priority": TaskPriority.HIGH.value,
                    "status": TaskStatus.PENDING.value,
                    "related_decision_id": str(decision_id),
                    "related_goal_id": str(goal_id) if goal_id else None,
                    "created_by": decision.get("decided_by") or decision.get("proposed_by"),
                }
                task_res = self.db.table("tasks").insert(task_data).execute()
                task_id = task_res.data[0]["id"]
                outcome = f"Created task {task_id}: {task_data['title']}"

            elif action_type == "reallocate_labor_task":
                target_emp = self._resolve_target_employee(company_id, department_id=dept_id, min_role="manager")
                task_priority = TaskPriority.URGENT.value if risk_level == "critical" else TaskPriority.HIGH.value
                task_data = {
                    "company_id": cid_str,
                    "title": f"Labor Reallocation: {action_payload.get('target_activity') or 'Operational Recovery'}",
                    "description": reasoning or "Reallocate operational field personnel and labor capacity.",
                    "assigned_to": target_emp,
                    "department_id": str(dept_id) if dept_id else None,
                    "priority": task_priority,
                    "status": TaskStatus.PENDING.value,
                    "related_decision_id": str(decision_id),
                    "related_goal_id": str(goal_id) if goal_id else None,
                    "created_by": decision.get("decided_by") or decision.get("proposed_by"),
                }
                task_res = self.db.table("tasks").insert(task_data).execute()
                task_id = task_res.data[0]["id"]
                outcome = f"Created labor task {task_id}: {task_data['title']}"

            elif action_type == "sales_escalation":
                target_emp = self._resolve_target_employee(company_id, department_id=dept_id, min_role="manager")
                notif_title = f"Sales Escalation: {action_payload.get('account') or 'Sales Target Alert'}"
                notif_data = {
                    "company_id": cid_str,
                    "recipient_id": target_emp,
                    "channel": NotificationChannel.IN_APP.value,
                    "title": notif_title,
                    "body": reasoning or "Immediate sales pipeline intervention and account review required.",
                    "related_decision_id": str(decision_id),
                    "status": NotificationStatus.PENDING.value,
                }
                notif_res = self.db.table("notifications").insert(notif_data).execute()
                notif_id = notif_res.data[0]["id"]
                outcome = f"Created notification {notif_id}: {notif_title}"

            elif action_type == "executive_risk_review":
                exec_emp = self._resolve_target_employee(company_id, min_role="executive")
                task_data = {
                    "company_id": cid_str,
                    "title": f"Executive Risk Review: {action_payload.get('risk_title') or 'Compounding Organizational Risk'}",
                    "description": reasoning or "Executive committee review required for open critical anomalies.",
                    "assigned_to": exec_emp,
                    "department_id": str(dept_id) if dept_id else None,
                    "priority": TaskPriority.URGENT.value,
                    "status": TaskStatus.PENDING.value,
                    "related_decision_id": str(decision_id),
                    "related_goal_id": str(goal_id) if goal_id else None,
                    "created_by": decision.get("decided_by") or decision.get("proposed_by"),
                }
                task_res = self.db.table("tasks").insert(task_data).execute()
                task_id = task_res.data[0]["id"]

                notif_data = {
                    "company_id": cid_str,
                    "recipient_id": exec_emp,
                    "channel": NotificationChannel.IN_APP.value,
                    "title": f"URGENT: Executive Risk Review Required",
                    "body": f"Critical risk review task created ({task_id}): {reasoning}",
                    "related_decision_id": str(decision_id),
                    "related_task_id": str(task_id),
                    "status": NotificationStatus.PENDING.value,
                }
                notif_res = self.db.table("notifications").insert(notif_data).execute()
                notif_id = notif_res.data[0]["id"]
                outcome = f"Created executive risk review task {task_id} and notification {notif_id}"

            else:
                raise ValueError(f"Unknown action_type '{action_type}'. Execution unsupported.")

            # Update decision to executed
            upd_data = {
                "status": DecisionStatus.EXECUTED.value,
                "executed_at": now_iso,
                "outcome": outcome,
            }
            upd_res = (
                self.db.table("decisions")
                .update(upd_data)
                .eq("id", str(decision_id))
                .execute()
            )

            # Mandatory institutional memory creation
            try:
                memory_data = {
                    "company_id": cid_str,
                    "memory_type": "decision",
                    "summary": f"Executed decision ({action_type}): {outcome}",
                    "detail": f"Outcome: {outcome}. Reasoning: {reasoning}. Action Payload: {json.dumps(action_payload)}",
                    "importance": 4,
                    "related_goal_id": str(goal_id) if goal_id else None,
                    "occurred_at": now_iso,
                }
                self.db.table("memory_entries").insert(memory_data).execute()
                logger.info(f"Recorded institutional memory for executed decision {decision_id}")
            except Exception as mem_err:
                logger.error(f"Failed to record institutional memory for decision {decision_id}: {mem_err}")

            logger.info(f"Executed decision {decision_id}: {outcome}")
            return DecisionRead(**upd_res.data[0])

        except Exception as e:
            logger.error(f"Execution failed for decision {decision_id}: {e}")
            fail_data = {
                "status": DecisionStatus.FAILED.value,
                "outcome": f"Execution failed: {str(e)}",
            }
            self.db.table("decisions").update(fail_data).eq("id", str(decision_id)).execute()
            raise e
