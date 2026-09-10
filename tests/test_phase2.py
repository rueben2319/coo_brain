import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.models.agent import AgentType
from app.models.decision import DecisionStatus, RiskLevel
from app.models.event import EventSeverity, EventStatus

client = TestClient(app)
DEV_COMPANY_ID = "ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279"
HEADERS = {"X-Dev-Company-Id": DEV_COMPANY_ID}


def test_phase2_models():
    """Verify Phase 2 enums and model initializations."""
    assert AgentType.FINANCE.value == "finance"
    assert AgentType.OPERATIONS.value == "operations"
    assert AgentType.SALES.value == "sales"
    assert AgentType.RISK.value == "risk"

    assert EventSeverity.CRITICAL.value == "critical"
    assert EventStatus.NEW.value == "new"
    assert RiskLevel.HIGH.value == "high"
    assert DecisionStatus.PROPOSED.value == "proposed"


def test_list_agents_endpoint():
    """Test GET /agents initializes default agent definitions."""
    res = client.get("/agents", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    agent_types = [a["agent_type"] for a in data]
    assert "finance" in agent_types
    assert "operations" in agent_types
    assert "sales" in agent_types
    assert "risk" in agent_types


def test_company_state_snapshot_endpoint():
    """Test GET /company-state/latest and POST /company-state/generate."""
    gen_res = client.post("/company-state/generate", headers=HEADERS)
    assert gen_res.status_code == 201
    snap = gen_res.data if hasattr(gen_res, "data") else gen_res.json()
    assert "metrics" in snap
    assert "summary" in snap

    get_res = client.get("/company-state/latest", headers=HEADERS)
    assert get_res.status_code == 200
    latest = get_res.json()
    assert latest["id"] == snap["id"]


def test_run_all_agents_endpoint():
    """Test POST /agents/run-all executes the 4 agents."""
    res = client.post("/agents/run-all", headers=HEADERS)
    assert res.status_code == 200
    responses = res.json()
    assert len(responses) == 4
    agent_types_run = [r["agent_type"] for r in responses]
    assert set(agent_types_run) == {"finance", "operations", "sales", "risk"}


def test_events_endpoint():
    """Test GET /events lists events."""
    res = client.get("/events", headers=HEADERS)
    assert res.status_code == 200
    events = res.json()
    assert isinstance(events, list)


def test_decisions_endpoint():
    """Test GET /decisions lists decisions."""
    res = client.get("/decisions", headers=HEADERS)
    assert res.status_code == 200
    decisions = res.json()
    assert isinstance(decisions, list)
