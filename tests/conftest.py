import os
import uuid
from typing import Generator
import pytest
from fastapi.testclient import TestClient

# Set test environment before imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SUPABASE_URL", "https://zhwulllprnbmbdkhhcol.supabase.co")
os.environ.setdefault(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpod3VsbGxwcm5ibWJka2hoY29sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg5NTgwNzMsImV4cCI6MjEwNDUzNDA3M30.5YelgF-ZXLwwvZqPOlTbdcrEnPgz6aE4ULSlwFH1k0o",
)


from app.main import app
from app.auth import get_auth_context, AuthContext, generate_dev_jwt

TEST_COMPANY_ID = uuid.UUID("ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279")
TEST_USER_ID = uuid.UUID("896cd5a0-248c-4220-b6dc-4822d211c239")


@pytest.fixture
def test_company_id() -> uuid.UUID:
    return TEST_COMPANY_ID


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return TEST_USER_ID


@pytest.fixture
def test_jwt(test_company_id: uuid.UUID, test_user_id: uuid.UUID) -> str:
    return generate_dev_jwt(
        company_id=test_company_id,
        user_id=test_user_id,
        email="test@sablefarming.com",
    )


@pytest.fixture
def client(test_jwt: str) -> Generator[TestClient, None, None]:
    with TestClient(app, headers={"Authorization": f"Bearer {test_jwt}"}) as c:
        yield c


@pytest.fixture
def unauthed_client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
