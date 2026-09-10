from enum import Enum
from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class EmployeeRole(str, Enum):
    owner = "owner"
    executive = "executive"
    manager = "manager"
    staff = "staff"
    ai_agent = "ai_agent"


class GoalStatus(str, Enum):
    not_started = "not_started"
    on_track = "on_track"
    at_risk = "at_risk"
    off_track = "off_track"
    achieved = "achieved"
    abandoned = "abandoned"


class PolicyType(str, Enum):
    spending_limit = "spending_limit"
    approval_rule = "approval_rule"
    sop = "sop"
    hr_policy = "hr_policy"
    compliance = "compliance"
    other = "other"


class MemoryType(str, Enum):
    experience = "experience"
    decision = "decision"
    lesson = "lesson"
    observation = "observation"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
