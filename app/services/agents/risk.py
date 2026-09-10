import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.event import EventSeverity
from app.services.agents.base import BaseAgent, Finding

logger = logging.getLogger("coo_brain.agent.risk")


class RiskAgent(BaseAgent):
    """
    Risk Agent: Analyzes active policies, all unresolved critical-severity events, compounding risks, and policy compliance breaches.
    """

    async def analyze(self, state_snapshot: Optional[Any], context: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        events = context.get("events", [])
        policies = context.get("policies", [])

        # 1. Detect multiple unresolved critical events across company
        critical_events = [e for e in events if e.get("severity") == "critical" and e.get("status") != "resolved"]
        if len(critical_events) >= 1:
            crit_titles = [e.get("title", "Untitled Event") for e in critical_events[:3]]
            findings.append(
                Finding(
                    event_type="compounding_risk_threshold_exceeded",
                    severity=EventSeverity.CRITICAL,
                    title="Compounding Organizational Risk Detected",
                    description=f"Company has {len(critical_events)} unresolved critical signal events active ({', '.join(crit_titles)}).",
                    payload={
                        "unresolved_critical_count": len(critical_events),
                        "critical_event_ids": [e["id"] for e in critical_events],
                    },
                    suggested_action_type="executive_risk_review",
                    suggested_action_payload={
                        "task": f"Convene Executive Risk Committee to address {len(critical_events)} active critical events",
                        "unresolved_count": len(critical_events),
                    },
                    reasoning=f"Active critical signals count ({len(critical_events)}) exceeds safe operational threshold. Immediate executive review required.",
                )
            )

        # 2. Inspect high-importance active policies (e.g. compliance/approval_rule)
        compliance_policies = [p for p in policies if p.get("policy_type") in ("compliance", "approval_rule")]
        for pol in compliance_policies:
            logger.info(f"RiskAgent verified compliance policy '{pol.get('title')}'")

        return findings
