from functools import lru_cache
from typing import Optional, Any
from supabase import create_client, Client
from app.config import get_settings, Settings


@lru_cache
def get_base_supabase_client() -> Client:
    settings = get_settings()
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not settings.supabase_url or not key:
        raise ValueError("Supabase URL and API Key must be configured in settings.")
    return create_client(settings.supabase_url, key)


def get_scoped_supabase_client(token: Optional[str] = None, company_id: Optional[Any] = None) -> Client:
    """
    Returns a Supabase client configured with the caller's JWT token
    and/or company_id header, ensuring RLS rules are respected.
    """
    settings = get_settings()
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    client = create_client(settings.supabase_url, key)
    if token:
        client.postgrest.auth(token)
    if company_id:
        client.postgrest.headers["x-dev-company-id"] = str(company_id)
    return client
