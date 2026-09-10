import uuid
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Header, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

security_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    company_id: UUID
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    role: Optional[str] = None
    token: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)


def extract_company_id_from_claims(claims: Dict[str, Any]) -> Optional[UUID]:
    # Check direct claim
    cid = claims.get("company_id")
    if cid:
        try:
            return UUID(str(cid))
        except (ValueError, TypeError):
            pass

    # Check app_metadata
    app_metadata = claims.get("app_metadata", {})
    if isinstance(app_metadata, dict):
        cid = app_metadata.get("company_id")
        if cid:
            try:
                return UUID(str(cid))
            except (ValueError, TypeError):
                pass

    # Check user_metadata
    user_metadata = claims.get("user_metadata", {})
    if isinstance(user_metadata, dict):
        cid = user_metadata.get("company_id")
        if cid:
            try:
                return UUID(str(cid))
            except (ValueError, TypeError):
                pass

    return None


async def get_auth_context(
    creds: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    x_dev_company_id: Optional[str] = Header(None, alias="X-Dev-Company-Id"),
    x_dev_user_id: Optional[str] = Header(None, alias="X-Dev-User-Id"),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """
    Extracts and validates the authentication context.
    The company_id is strictly derived from the caller's JWT (or dev headers in development mode).
    Request bodies are never trusted for scoping.
    """
    token = creds.credentials if creds else None
    claims: Dict[str, Any] = {}

    if token:
        try:
            if settings.supabase_jwt_secret:
                claims = jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
            else:
                # In development or when no secret is configured, decode without signature verification
                claims = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_aud": False},
                )
        except jwt.PyJWTError as e:
            if settings.environment != "development":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid or expired JWT: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    company_id = extract_company_id_from_claims(claims)

    user_id = None
    sub = claims.get("sub")
    if sub:
        try:
            user_id = UUID(str(sub))
        except (ValueError, TypeError):
            pass

    email = claims.get("email")
    role = claims.get("role")

    # In development mode with dev-auth enabled, allow dev headers or fallback to existing company
    if not company_id and settings.environment == "development" and settings.allow_dev_auth_headers:
        if x_dev_company_id:
            try:
                company_id = UUID(x_dev_company_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid X-Dev-Company-Id UUID format",
                )
        else:
            # Fallback to default existing company in the database
            company_id = UUID("ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279")

        if x_dev_user_id:
            try:
                user_id = UUID(x_dev_user_id)
            except ValueError:
                pass
        elif not user_id:
            user_id = UUID("896cd5a0-248c-4220-b6dc-4822d211c239")

    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: company_id claim is missing from JWT",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthContext(
        company_id=company_id,
        user_id=user_id,
        email=email,
        role=role,
        token=token,
        claims=claims,
    )


def generate_dev_jwt(
    company_id: UUID,
    user_id: Optional[UUID] = None,
    email: Optional[str] = None,
    role: str = "authenticated",
    secret: Optional[str] = None,
) -> str:
    """Generates a signed JWT with company_id for curl / testing."""
    payload = {
        "sub": str(user_id or uuid.uuid4()),
        "company_id": str(company_id),
        "email": email or "test@example.com",
        "role": role,
        "app_metadata": {"company_id": str(company_id)},
    }
    return jwt.encode(payload, secret or "secret", algorithm="HS256")
