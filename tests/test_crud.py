import uuid
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.companies import get_db as get_companies_db
from app.routers.departments import get_db as get_departments_db
from app.routers.employees import get_db as get_employees_db
from app.routers.goals import get_db as get_goals_db
from app.routers.policies import get_db as get_policies_db
from app.routers.documents import get_db as get_documents_db
from app.routers.memory import get_db as get_memory_db


@pytest.fixture
def mock_db():
    client = MagicMock()
    return client


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "coo_brain"


def test_list_companies(client: TestClient, test_company_id: uuid.UUID):
    mock = MagicMock()
    mock.table().select().eq().execute.return_value.data = [
        {
            "id": str(test_company_id),
            "name": "Sable Farming Company Limited",
            "industry": "Agriculture",
            "mission": "Sustainable farming",
            "vision": "Leading agro-producer",
            "timezone": "Africa/Blantyre",
            "created_at": "2026-09-10T06:20:34Z",
            "updated_at": "2026-09-10T06:20:34Z",
        }
    ]
    app.dependency_overrides[get_companies_db] = lambda: mock

    response = client.get("/companies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Sable Farming Company Limited"

    app.dependency_overrides.clear()


def test_create_goal(client: TestClient, test_company_id: uuid.UUID):
    mock = MagicMock()
    goal_id = str(uuid.uuid4())
    mock.table().insert().execute.return_value.data = [
        {
            "id": goal_id,
            "company_id": str(test_company_id),
            "title": "Boost Macadamia Yield",
            "metric_name": "yield_tons",
            "target_value": 1500.0,
            "current_value": 300.0,
            "unit": "tons",
            "status": "on_track",
            "starts_at": "2026-01-01",
            "due_at": "2026-12-31",
            "created_at": "2026-09-10T06:20:34Z",
            "updated_at": "2026-09-10T06:20:34Z",
        }
    ]
    app.dependency_overrides[get_goals_db] = lambda: mock

    payload = {
        "title": "Boost Macadamia Yield",
        "metric_name": "yield_tons",
        "target_value": 1500.0,
        "current_value": 300.0,
        "unit": "tons",
        "status": "on_track",
        "starts_at": "2026-01-01",
        "due_at": "2026-12-31",
    }
    response = client.post("/goals", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == goal_id
    assert data["title"] == "Boost Macadamia Yield"

    app.dependency_overrides.clear()


def test_create_memory_direct(client: TestClient, test_company_id: uuid.UUID):
    mock = MagicMock()
    mem_id = str(uuid.uuid4())
    mock.table().insert().execute.return_value.data = [
        {
            "id": mem_id,
            "company_id": str(test_company_id),
            "memory_type": "decision",
            "summary": "Switched to solar-powered drip irrigation for Sector 4",
            "detail": "Approved budget 45,000,000 MWK after pump failure",
            "importance": 5,
            "occurred_at": "2026-09-08T10:00:00Z",
            "created_at": "2026-09-10T06:20:34Z",
        }
    ]
    app.dependency_overrides[get_memory_db] = lambda: mock

    payload = {
        "memory_type": "decision",
        "summary": "Switched to solar-powered drip irrigation for Sector 4",
        "detail": "Approved budget 45,000,000 MWK after pump failure",
        "importance": 5,
    }
    response = client.post("/memory", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == mem_id
    assert data["memory_type"] == "decision"
    assert data["importance"] == 5

    app.dependency_overrides.clear()
