from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.auth import AuthContext, get_auth_context
from app.database import get_scoped_supabase_client
from app.models.agent import (
    AgentDefinitionCreate,
    AgentDefinitionRead,
    AgentDefinitionUpdate,
    AgentRunResponse,
)
from app.services.agents.runner import AgentRunner

router = APIRouter(prefix="/agents", tags=["Agents"])


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    return get_scoped_supabase_client(token=auth.token, company_id=auth.company_id)


@router.get("", response_model=List[AgentDefinitionRead])
async def list_agents(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """List agent definitions for the company (initializes defaults if empty)."""
    runner = AgentRunner(db)
    agent_defs = await runner.ensure_agent_definitions(auth.company_id)
    return agent_defs


@router.get("/{agent_id}", response_model=AgentDefinitionRead)
async def get_agent(
    agent_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Get single agent definition."""
    res = (
        db.table("agent_definitions")
        .select("*")
        .eq("id", str(agent_id))
        .eq("company_id", str(auth.company_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent definition not found")
    return AgentDefinitionRead(**res.data[0])


@router.post("/{agent_id}/run", response_model=AgentRunResponse)
async def run_single_agent(
    agent_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Manually trigger a run for a single agent."""
    runner = AgentRunner(db)
    try:
        return await runner.run_agent_by_id(agent_id, auth.company_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/run-all", response_model=List[AgentRunResponse])
async def run_all_agents(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
):
    """Trigger runs for all active agents in sequence."""
    runner = AgentRunner(db)
    return await runner.run_all_agents(auth.company_id)
