import uuid
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.coo import get_db as get_coo_db
from app.models.chat import ChatResponse


def test_coo_chat_endpoint(client: TestClient, test_company_id: uuid.UUID):
    mock = MagicMock()
    conv_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    mem_id = str(uuid.uuid4())

    # Mock coo_conversations select (not found, so insert)
    mock.table().select().eq().eq().execute.return_value.data = []
    # Mock coo_conversations insert
    mock.table().insert().execute.return_value.data = [{"id": conv_id}]

    # Mock company select
    mock.table().select().eq().execute.return_value.data = [
        {
            "id": str(test_company_id),
            "name": "Sable Farming Company Limited",
            "mission": "Excellence in agribusiness",
            "vision": "Leading African producer",
            "industry": "Agriculture",
        }
    ]

    # Mock RPC for document chunks
    mock.rpc().execute.return_value.data = [
        {
            "id": str(uuid.uuid4()),
            "document_id": doc_id,
            "chunk_index": 0,
            "content": "Irrigation guidelines mandate soil moisture monitoring every 4 hours.",
            "document_title": "Irrigation SOP 2026",
            "similarity": 0.89,
        }
    ]

    # Mock goals select
    mock.table().select().eq().not_.in_().limit().execute.return_value.data = [
        {
            "id": str(uuid.uuid4()),
            "title": "Irrigation Efficiency",
            "status": "on_track",
            "target_value": 90,
            "current_value": 75,
            "unit": "%",
            "due_at": "2026-12-31",
        }
    ]

    # Mock policies select
    mock.table().select().eq().eq().limit().execute.return_value.data = [
        {
            "id": str(uuid.uuid4()),
            "title": "Water Conservation Policy",
            "policy_type": "sop",
            "description": "Rules for dry season water pumping",
            "rule": {"max_daily_hours": 6},
            "is_active": True,
        }
    ]

    # Mock coo_messages select
    mock.table().select().eq().order().limit().execute.return_value.data = []

    app.dependency_overrides[get_coo_db] = lambda: mock

    # Mock LLM service response
    with patch("app.services.brain.get_llm_service") as mock_llm_getter:
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(
            return_value="Based on [DOC-" + doc_id + "], you should ensure 4-hour checks."
        )
        mock_llm_getter.return_value = mock_llm

        payload = {
            "message": "What is our procedure for irrigation and dry season pumping?",
        }
        response = client.post("/coo/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "reply" in data
        assert doc_id in data["cited_document_ids"]
        assert "conversation_id" in data
        assert "message_id" in data

    app.dependency_overrides.clear()
