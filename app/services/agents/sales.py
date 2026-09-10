import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.event import EventSeverity
from app.services.agents.base import BaseAgent, Finding

logger = logging.getLogger("coo_brain.agent.sales")


class SalesAgent(BaseAgent):
    """
    Sales Agent: Analyzes revenue/sales goals, stagnant progress, conversion rates, and market performance.
    """

    async def analyze(self, state_snapshot: Optional[Any], context: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        goals = context.get("goals", [])

        sales_keywords = ["sales", "revenue", "export", "client", "contract", "volume", "market", "customer"]

        for goal in goals:
            title = goal.get("title", "")
            metric_name = (goal.get("metric_name") or "").lower()
            status = goal.get("status")

            is_sales = any(kw in metric_name or kw in title.lower() for kw in sales_keywords)
            if not is_sales:
                continue

            current = goal.get("current_value") or 0.0
            target = goal.get("target_value") or 1.0

            if status in ("at_risk", "off_track") or (target > 0 and current / target < 0.5):
                findings.append(
                    Finding(
                        event_type="sales_stagnation_alert",
                        severity=EventSeverity.WARNING,
                        title=f"Sales Performance Lag: {title}",
                        description=f"Sales goal '{title}' exhibits performance lag with current value {current} vs target {target}.",
                        payload={
                            "goal_id": goal["id"],
                            "target_value": target,
                            "current_value": current,
                            "status": status,
                        },
                        related_goal_id=UUID(goal["id"]),
                        related_department_id=UUID(goal["department_id"]) if goal.get("department_id") else None,
                        suggested_action_type="sales_department_escalation",
                        suggested_action_payload={
                            "task": f"Escalate sales milestone review for {title} to Commercial Head",
                            "department_id": goal.get("department_id"),
                        },
                        reasoning=f"Sales metric for '{title}' is lagging ({current}/{target}). Sales escalation proposed.",
                    )
                )

        return findings
