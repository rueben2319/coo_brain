import logging
from typing import Dict, List, Optional, Type
from uuid import UUID
from supabase import Client

from app.models.agent import AgentDefinitionRead, AgentRunResponse, AgentType
from app.services.agents.base import BaseAgent
from app.services.agents.finance import FinanceAgent
from app.services.agents.operations import OperationsAgent
from app.services.agents.sales import SalesAgent
from app.services.agents.risk import RiskAgent

logger = logging.getLogger("coo_brain.agent.runner")

AGENT_MAP: Dict[AgentType, Type[BaseAgent]] = {
    AgentType.FINANCE: FinanceAgent,
    AgentType.OPERATIONS: OperationsAgent,
    AgentType.SALES: SalesAgent,
    AgentType.RISK: RiskAgent,
}

DEFAULT_AGENT_PROMPTS = {
    AgentType.FINANCE: {
        "name": "Finance Agent",
        "system_prompt": "You are the AI Finance Agent. Monitor budgets, spending limits, financial goals, and cost overruns across departments.",
        "watch_config": {"budget_variance_threshold_pct": 10.0, "scan_interval_hours": 24},
    },
    AgentType.OPERATIONS: {
        "name": "Operations Agent",
        "system_prompt": "You are the AI Operations Agent. Monitor estate production, irrigation SOPs, harvest schedules, and equipment efficiency.",
        "watch_config": {"harvest_delay_threshold_days": 2, "scan_interval_hours": 12},
    },
    AgentType.SALES: {
        "name": "Sales Agent",
        "system_prompt": "You are the AI Sales Agent. Monitor export sales goals, customer contracts, revenue targets, and market pricing.",
        "watch_config": {"stagnant_goal_cycles": 2, "scan_interval_hours": 24},
    },
    AgentType.RISK: {
        "name": "Risk Agent",
        "system_prompt": "You are the AI Risk Agent. Monitor compliance policies, unresolved critical events, and compounding enterprise risks.",
        "watch_config": {"critical_event_threshold": 1, "scan_interval_hours": 6},
    },
}


class AgentRunner:
    def __init__(self, db: Client):
        self.db = db

    async def ensure_agent_definitions(self, company_id: UUID) -> List[AgentDefinitionRead]:
        """
        Ensures an employee row (role='ai_agent') and agent_definitions row exist
        for each of the 4 agent types for the given company.
        """
        cid_str = str(company_id)
        definitions: List[AgentDefinitionRead] = []

        for agent_type in AgentType:
            type_str = agent_type.value
            existing_def = (
                self.db.table("agent_definitions")
                .select("*")
                .eq("company_id", cid_str)
                .eq("agent_type", type_str)
                .eq("is_active", True)
                .execute()
            )

            if existing_def.data:
                definitions.append(AgentDefinitionRead(**existing_def.data[0]))
                continue

            # Check if employee row exists for this agent
            agent_info = DEFAULT_AGENT_PROMPTS[agent_type]
            agent_name = agent_info["name"]

            emp_res = (
                self.db.table("employees")
                .select("*")
                .eq("company_id", cid_str)
                .eq("role", "ai_agent")
                .eq("full_name", agent_name)
                .execute()
            )

            employee_id = None
            if emp_res.data:
                employee_id = emp_res.data[0]["id"]
            else:
                new_emp = {
                    "company_id": cid_str,
                    "full_name": agent_name,
                    "email": f"{type_str}.agent@coo-brain.internal",
                    "role": "ai_agent",
                    "title": f"AI {type_str.capitalize()} Intelligence Officer",
                    "is_active": True,
                }
                inserted_emp = self.db.table("employees").insert(new_emp).execute()
                employee_id = inserted_emp.data[0]["id"]

            # Create agent definition
            new_def = {
                "company_id": cid_str,
                "employee_id": employee_id,
                "agent_type": type_str,
                "name": agent_name,
                "system_prompt": agent_info["system_prompt"],
                "watch_config": agent_info["watch_config"],
                "is_active": True,
            }
            inserted_def = self.db.table("agent_definitions").insert(new_def).execute()
            definitions.append(AgentDefinitionRead(**inserted_def.data[0]))
            logger.info(f"Initialized agent definition for '{agent_name}' ({type_str}) in company {company_id}")

        return definitions

    async def run_agent_by_id(self, agent_id: UUID, company_id: UUID) -> AgentRunResponse:
        res = (
            self.db.table("agent_definitions")
            .select("*")
            .eq("id", str(agent_id))
            .eq("company_id", str(company_id))
            .execute()
        )
        if not res.data:
            raise ValueError(f"Agent definition {agent_id} not found for company {company_id}")

        agent_def = AgentDefinitionRead(**res.data[0])
        agent_type = AgentType(agent_def.agent_type)
        agent_cls = AGENT_MAP[agent_type]

        agent = agent_cls(self.db, agent_def)
        return await agent.run()

    async def run_all_agents(self, company_id: UUID) -> List[AgentRunResponse]:
        agent_defs = await self.ensure_agent_definitions(company_id)
        responses: List[AgentRunResponse] = []

        for agent_def in agent_defs:
            if not agent_def.is_active:
                continue
            agent_type = AgentType(agent_def.agent_type)
            agent_cls = AGENT_MAP[agent_type]
            agent = agent_cls(self.db, agent_def)
            resp = await agent.run()
            responses.append(resp)

        return responses
