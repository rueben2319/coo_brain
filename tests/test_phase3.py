import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.task import TaskPriority, TaskStatus, TaskCreate, TaskRead
from app.models.notification import NotificationChannel, NotificationStatus, NotificationCreate, NotificationRead
from app.models.purchase_request import PurchaseRequestStatus, PurchaseRequestCreate, PurchaseRequestRead
from app.models.report import ReportType, ReportGenerateRequest, ReportRead
from app.models.decision import DecisionStatus, RiskLevel
from app.services.decision_engine import ROLE_HIERARCHY

client = TestClient(app)

TEST_COMPANY_ID = "ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279"
TEST_OWNER_USER_ID = "896cd5a0-248c-4220-b6dc-4822d211c239"


def test_phase3_models_and_enums():
    # Tasks
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"
    assert TaskStatus.BLOCKED.value == "blocked"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.CANCELLED.value == "cancelled"
    assert TaskPriority.LOW.value == "low"
    assert TaskPriority.NORMAL.value == "normal"
    assert TaskPriority.HIGH.value == "high"
    assert TaskPriority.URGENT.value == "urgent"

    # Notifications
    assert NotificationChannel.IN_APP.value == "in_app"
    assert NotificationChannel.EMAIL.value == "email"
    assert NotificationChannel.SMS.value == "sms"
    assert NotificationStatus.PENDING.value == "pending"
    assert NotificationStatus.SENT.value == "sent"
    assert NotificationStatus.FAILED.value == "failed"
    assert NotificationStatus.READ.value == "read"

    # Purchase requests
    assert PurchaseRequestStatus.DRAFT.value == "draft"
    assert PurchaseRequestStatus.PENDING_APPROVAL.value == "pending_approval"
    assert PurchaseRequestStatus.APPROVED.value == "approved"
    assert PurchaseRequestStatus.REJECTED.value == "rejected"
    assert PurchaseRequestStatus.ORDERED.value == "ordered"
    assert PurchaseRequestStatus.RECEIVED.value == "received"
    assert PurchaseRequestStatus.CANCELLED.value == "cancelled"

    # Reports
    assert ReportType.WEEKLY_SUMMARY.value == "weekly_summary"
    assert ReportType.GOAL_PROGRESS.value == "goal_progress"
    assert ReportType.FINANCIAL_REVIEW.value == "financial_review"
    assert ReportType.RISK_REVIEW.value == "risk_review"
    assert ReportType.CUSTOM.value == "custom"

    # Role Hierarchy
    assert ROLE_HIERARCHY["staff"] < ROLE_HIERARCHY["manager"]
    assert ROLE_HIERARCHY["manager"] < ROLE_HIERARCHY["executive"]
    assert ROLE_HIERARCHY["executive"] < ROLE_HIERARCHY["owner"]


def test_list_tasks_endpoint():
    response = client.get(
        "/tasks",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_notifications_endpoint():
    response = client.get(
        "/notifications",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_purchase_requests_endpoint():
    response = client.get(
        "/purchase-requests",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_reports_endpoint():
    response = client.get(
        "/reports",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_calendar_events_endpoint():
    response = client.get(
        "/calendar-events",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_generate_report_endpoint():
    response = client.post(
        "/reports/generate",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
        json={
            "report_type": "weekly_summary",
            "title": "Unit Test Weekly Summary Report",
        },
    )
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["report_type"] == "weekly_summary"
    assert "content" in data
    assert len(data["content"]) > 0

    # Cleanup generated report
    rep_id = data["id"]
    client.delete(
        f"/reports/{rep_id}",
        headers={"X-Dev-Company-Id": TEST_COMPANY_ID, "X-Dev-User-Id": TEST_OWNER_USER_ID},
    )
