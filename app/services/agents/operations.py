from datetime import datetime, date
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.event import EventSeverity
from app.services.agents.base import BaseAgent, Finding

logger = logging.getLogger("coo_brain.agent.operations")


class OperationsAgent(BaseAgent):
    """
    Operations Agent: Analyzes production & operations goals, SOP compliance, harvest deadlines, and schedule delays.
    """

    async def analyze(self, state_snapshot: Optional[Any], context: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        goals = context.get("goals", [])

        # Inspect operations/production goals
        ops_keywords = ["production", "harvest", "yield", "irrigation", "borehole", "estate", "processing", "tons", "plant"]

        for goal in goals:
            title = goal.get("title", "")
            metric_name = (goal.get("metric_name") or "").lower()
            status = goal.get("status")
            due_at_str = goal.get("due_at")

            is_ops = any(kw in metric_name or kw in title.lower() for kw in ops_keywords)
            if not is_ops:
                continue

            if status in ("at_risk", "off_track"):
                due_info = f" (Due date: {due_at_str})" if due_at_str else ""
                severity = EventSeverity.CRITICAL if status == "off_track" else EventSeverity.WARNING

                findings.append(
                    Finding(
                        event_type="operational_goal_off_track",
                        severity=severity,
                        title=f"Operations Goal {status.upper()}: {title}",
                        description=f"Operational production goal '{title}' is marked as '{status}'{due_info}.",
                        payload={
                            "goal_id": goal["id"],
                            "target_value": goal.get("target_value"),
                            "current_value": goal.get("current_value"),
                            "metric_name": goal.get("metric_name"),
                            "status": status,
                            "due_at": due_at_str,
                        },
                        related_goal_id=UUID(goal["id"]),
                        related_department_id=UUID(goal["department_id"]) if goal.get("department_id") else None,
                        suggested_action_type="reallocate_labor_task",
                        suggested_action_payload={
                            "task": f"Reallocate labor and equipment resources to accelerate operational milestone for {title}",
                            "department_id": goal.get("department_id"),
                        },
                        reasoning=f"Operations goal '{title}' is {status}. Resource reallocation recommended to protect target deadlines.",
                    )
                )

        return findings
