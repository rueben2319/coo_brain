import asyncio
import uuid
import pytest
from app.auth import (
    extract_company_id_from_claims,
    generate_dev_jwt,
    get_auth_context,
    AuthContext,
)
from app.config import Settings


def test_extract_company_id_direct():
    cid = uuid.uuid4()
    claims = {"company_id": str(cid)}
    extracted = extract_company_id_from_claims(claims)
    assert extracted == cid


def test_extract_company_id_app_metadata():
    cid = uuid.uuid4()
    claims = {"app_metadata": {"company_id": str(cid)}}
    extracted = extract_company_id_from_claims(claims)
    assert extracted == cid


def test_extract_company_id_user_metadata():
    cid = uuid.uuid4()
    claims = {"user_metadata": {"company_id": str(cid)}}
    extracted = extract_company_id_from_claims(claims)
    assert extracted == cid


def test_extract_company_id_missing():
    claims = {"sub": str(uuid.uuid4()), "role": "authenticated"}
    extracted = extract_company_id_from_claims(claims)
    assert extracted is None


def test_get_auth_context_dev_headers():
    cid = uuid.uuid4()
    uid = uuid.uuid4()
    settings = Settings(environment="development")

    ctx = asyncio.run(
        get_auth_context(
            creds=None,
            x_dev_company_id=str(cid),
            x_dev_user_id=str(uid),
            settings=settings,
        )
    )
    assert ctx.company_id == cid
    assert ctx.user_id == uid
