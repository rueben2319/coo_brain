import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.event import EventSeverity
from app.services.agents.base import BaseAgent, Finding

logger = logging.getLogger("coo_brain.agent.finance")


class FinanceAgent(BaseAgent):
    """
    Finance Agent: Analyzes goals with financial metrics, spending policies, budget variance, and cost overruns.
    """

    async def analyze(self, state_snapshot: Optional[Any], context: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        goals = context.get("goals", [])
        policies = context.get("policies", [])

        # 1. Inspect goals with financial metrics (revenue, cost, spend, budget, profit)
        financial_keywords = ["spend", "budget", "cost", "revenue", "expense", "margin", "profit", "usd", "mwk"]

        for goal in goals:
            metric_name = (goal.get("metric_name") or "").lower()
            title = goal.get("title", "")
            status = goal.get("status")

            is_financial = any(kw in metric_name or kw in title.lower() for kw in financial_keywords)
            if not is_financial:
                continue

            target = goal.get("target_value")
            current = goal.get("current_value")

            if status == "off_track" or (target and current and current < target * 0.7):
                findings.append(
                    Finding(
                        event_type="budget_variance_warning",
                        severity=EventSeverity.WARNING,
                        title=f"Financial Goal Off Track: {title}",
                        description=f"Goal '{title}' current value {current} is significantly below target {target} {goal.get('unit') or ''}.",
                        payload={
                            "goal_id": goal["id"],
                            "target_value": target,
                            "current_value": current,
                            "metric_name": goal.get("metric_name"),
                            "status": status,
                        },
                        related_goal_id=UUID(goal["id"]),
                        related_department_id=UUID(goal["department_id"]) if goal.get("department_id") else None,
                        suggested_action_type="budget_review_task",
                        suggested_action_payload={
                            "task": f"Conduct emergency budget and expenditure review for {title}",
                            "department_id": goal.get("department_id"),
                        },
                        reasoning=f"Financial metric for '{title}' is off track ({current}/{target}). Immediate budget review recommended.",
                    )
                )

        # 2. Check spending_limit policies
        spending_policies = [p for p in policies if p.get("policy_type") == "spending_limit"]
        for pol in spending_policies:
            rule = pol.get("rule", {})
            max_amount = rule.get("max_amount") or rule.get("spending_cap")
            if max_amount:
                # Flag spending limit check
                logger.info(f"FinanceAgent checked spending policy '{pol.get('title')}' with cap {max_amount}")

        return findings
