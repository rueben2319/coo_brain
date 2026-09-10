from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from supabase import Client

from app.models.agent import AgentDefinitionRead, AgentRunResponse, AgentType
from app.models.decision import DecisionRead, RiskLevel
from app.models.event import EventCreate, EventRead, EventSeverity, EventStatus
from app.services.company_state import CompanyStateService
from app.services.decision_engine import DecisionEngineService

logger = logging.getLogger("coo_brain.agent.base")


class Finding(dict):
    """
    Structured detection finding produced by an agent.
    Keys:
    - event_type (str)
    - severity (EventSeverity)
    - title (str)
    - description (str)
    - payload (dict)
    - related_goal_id (Optional[UUID])
    - related_department_id (Optional[UUID])
    - suggested_action_type (Optional[str])
    - suggested_action_payload (Optional[dict])
    - reasoning (Optional[str])
    """
    pass


class BaseAgent(ABC):
    def __init__(self, db: Client, agent_def: AgentDefinitionRead):
        self.db = db
        self.agent_def = agent_def
        self.company_id = agent_def.company_id
        self.employee_id = agent_def.employee_id
        self.company_state_service = CompanyStateService(db)
        self.decision_engine = DecisionEngineService(db)

    @abstractmethod
    async def analyze(self, state_snapshot: Optional[Any], context: Dict[str, Any]) -> List[Finding]:
        """Domain-specific analysis implemented by concrete agents."""
        pass

    async def gather_context(self) -> Dict[str, Any]:

        """Pulls domain-relevant goals, policies, events, and department info."""
        cid_str = str(self.company_id)
        goals = self.db.table("goals").select("*").eq("company_id", cid_str).execute().data or []
        policies = self.db.table("policies").select("*").eq("company_id", cid_str).eq("is_active", True).execute().data or []
        events = (
            self.db.table("events")
            .select("*")
            .eq("company_id", cid_str)
            .neq("status", "resolved")
            .neq("status", "dismissed")
            .execute()
            .data or []
        )
        departments = self.db.table("departments").select("*").eq("company_id", cid_str).execute().data or []

        return {
            "goals": goals,
            "policies": policies,
            "events": events,
            "departments": departments,
        }

    def _map_severity_to_risk(self, severity: EventSeverity) -> RiskLevel:
        if severity == EventSeverity.CRITICAL:
            return RiskLevel.HIGH
        elif severity == EventSeverity.WARNING:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    async def run(self) -> AgentRunResponse:
        logger.info(f"Running agent '{self.agent_def.name}' ({self.agent_def.agent_type})...")
        
        # 1. Fetch latest company state snapshot + domain context
        snapshot = await self.company_state_service.get_latest_snapshot(self.company_id)
        context = await self.gather_context()

        # 2. Run agent domain analysis
        findings = await self.analyze(snapshot, context)

        events_created = 0
        decisions_proposed = 0

        # 3. Process findings
        for finding in findings:
            event_type = finding.get("event_type", "anomaly_detected")
            severity = finding.get("severity", EventSeverity.INFO)
            title = finding.get("title", f"Agent Alert: {event_type}")
            description = finding.get("description", "")
            payload = finding.get("payload", {})
            related_goal_id = finding.get("related_goal_id")
            related_dept_id = finding.get("related_department_id")

            # Check if an open event of same type & title already exists to prevent duplicate spam
            existing_event = (
                self.db.table("events")
                .select("id")
                .eq("company_id", str(self.company_id))
                .eq("event_type", event_type)
                .eq("title", title)
                .neq("status", "resolved")
                .neq("status", "dismissed")
                .execute()
            )

            if existing_event.data:
                logger.info(f"Skipping duplicate event creation for '{title}' (already open).")
                continue

            # Insert Event
            event_data = {
                "company_id": str(self.company_id),
                "source_agent_id": str(self.agent_def.id),
                "event_type": event_type,
                "severity": severity.value if isinstance(severity, EventSeverity) else severity,
                "title": title,
                "description": description,
                "payload": payload,
                "related_goal_id": str(related_goal_id) if related_goal_id else None,
                "related_department_id": str(related_dept_id) if related_dept_id else None,
                "status": EventStatus.NEW.value,
            }

            event_res = self.db.table("events").insert(event_data).execute()
            event_id = event_res.data[0]["id"]
            events_created += 1

            # 4. Propose decision for warning or critical findings if suggested_action_type is present
            suggested_action_type = finding.get("suggested_action_type")
            if severity in (EventSeverity.WARNING, EventSeverity.CRITICAL) and suggested_action_type:
                suggested_action_payload = finding.get("suggested_action_payload", {})
                reasoning = finding.get("reasoning", description)
                risk_level = self._map_severity_to_risk(severity)

                decision = await self.decision_engine.propose_decision(
                    company_id=self.company_id,
                    proposed_by=self.employee_id,
                    action_type=suggested_action_type,
                    action_payload=suggested_action_payload,
                    reasoning=reasoning,
                    risk_level=risk_level,
                    department_id=related_dept_id,
                    related_goal_id=related_goal_id,
                )
                decisions_proposed += 1

                # Link event to resulting decision
                self.db.table("events").update({"resulting_decision_id": str(decision.id)}).eq("id", event_id).execute()

        # 5. Update agent's last_run_at
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.table("agent_definitions").update({"last_run_at": now_iso}).eq("id", str(self.agent_def.id)).execute()

        summary = f"Agent '{self.agent_def.name}' run complete: {events_created} events created, {decisions_proposed} decisions proposed."
        logger.info(summary)

        return AgentRunResponse(
            agent_type=self.agent_def.agent_type,
            events_created=events_created,
            decisions_proposed=decisions_proposed,
            summary=summary,
        )
