from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.common import AppBaseModel



class AgentType(str, Enum):
    FINANCE = "finance"
    OPERATIONS = "operations"
    SALES = "sales"
    RISK = "risk"


class AgentDefinitionBase(BaseModel):
    agent_type: AgentType
    name: str
    system_prompt: str
    watch_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AgentDefinitionCreate(AgentDefinitionBase):
    company_id: Optional[UUID] = None
    employee_id: Optional[UUID] = None


class AgentDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    watch_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AgentDefinitionRead(AgentDefinitionBase, AppBaseModel):
    id: UUID
    company_id: UUID
    employee_id: UUID
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime



class AgentRunResponse(BaseModel):
    agent_type: AgentType
    events_created: int
    decisions_proposed: int
    summary: str
