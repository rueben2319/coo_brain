import uuid
from datetime import date, datetime
import pytest
from pydantic import ValidationError

from app.models import (
    EmployeeRole,
    GoalStatus,
    PolicyType,
    MemoryType,
    MessageRole,
    CompanyCreate,
    CompanyRead,
    DepartmentCreate,
    DepartmentRead,
    EmployeeCreate,
    EmployeeRead,
    GoalCreate,
    GoalRead,
    PolicyCreate,
    PolicyRead,
    DocumentCreate,
    DocumentRead,
    MemoryEntryCreate,
    MemoryEntryRead,
    ChatRequest,
    ChatResponse,
)


def test_employee_role_enum():
    assert EmployeeRole.owner == "owner"
    assert EmployeeRole.executive == "executive"
    assert EmployeeRole.manager == "manager"
    assert EmployeeRole.staff == "staff"
    assert EmployeeRole.ai_agent == "ai_agent"


def test_goal_status_enum():
    assert GoalStatus.not_started == "not_started"
    assert GoalStatus.on_track == "on_track"
    assert GoalStatus.at_risk == "at_risk"
    assert GoalStatus.off_track == "off_track"
    assert GoalStatus.achieved == "achieved"
    assert GoalStatus.abandoned == "abandoned"


def test_policy_type_enum():
    assert PolicyType.spending_limit == "spending_limit"
    assert PolicyType.approval_rule == "approval_rule"
    assert PolicyType.sop == "sop"
    assert PolicyType.hr_policy == "hr_policy"
    assert PolicyType.compliance == "compliance"
    assert PolicyType.other == "other"


def test_memory_type_enum():
    assert MemoryType.experience == "experience"
    assert MemoryType.decision == "decision"
    assert MemoryType.lesson == "lesson"
    assert MemoryType.observation == "observation"


def test_company_models():
    comp_create = CompanyCreate(name="Acme Corp", industry="Tech")
    assert comp_create.name == "Acme Corp"
    assert comp_create.timezone == "Africa/Blantyre"

    comp_read = CompanyRead(
        id=uuid.uuid4(),
        name="Acme Corp",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert comp_read.name == "Acme Corp"


def test_employee_models():
    emp = EmployeeCreate(
        full_name="John Doe",
        email="john@example.com",
        role=EmployeeRole.executive,
        title="COO",
    )
    assert emp.role == EmployeeRole.executive
    assert emp.is_active is True


def test_goal_models():
    goal = GoalCreate(
        title="Expand yield by 20%",
        metric_name="metric_tons",
        target_value=5000.0,
        current_value=1200.0,
        unit="tons",
        status=GoalStatus.on_track,
        due_at=date(2026, 12, 31),
    )
    assert goal.target_value == 5000.0
    assert goal.status == GoalStatus.on_track


def test_policy_models():
    policy = PolicyCreate(
        title="Expense Approval",
        policy_type=PolicyType.spending_limit,
        rule={"max_amount": 500000, "currency": "MWK"},
    )
    assert policy.rule["currency"] == "MWK"


def test_memory_models():
    # Valid importance 1-5
    mem = MemoryEntryCreate(
        memory_type=MemoryType.lesson,
        summary="Delayed harvest causes 10% quality drop",
        importance=4,
    )
    assert mem.importance == 4

    # Invalid importance
    with pytest.raises(ValidationError):
        MemoryEntryCreate(
            memory_type=MemoryType.lesson,
            summary="Invalid",
            importance=10,
        )


def test_chat_models():
    req = ChatRequest(message="What are our active Q3 goals?")
    assert req.message == "What are our active Q3 goals?"
    assert req.conversation_id is None

    res = ChatResponse(
        conversation_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        reply="Here are the active goals...",
        cited_document_ids=[uuid.uuid4()],
        cited_memory_ids=[],
    )
    assert len(res.cited_document_ids) == 1
