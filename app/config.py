from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase Settings
    supabase_url: str = "https://zhwulllprnbmbdkhhcol.supabase.co"
    supabase_anon_key: str = ""
    supabase_service_role_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None

    # Ollama Settings
    ollama_api_key: Optional[str] = None
    ollama_base_url: str = "https://ollama.com/api"
    ollama_chat_model: str = "llama3.3"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_embed_base_url: Optional[str] = None

    # Application Settings
    environment: str = "development"
    allow_dev_auth_headers: bool = True
    vector_dimension: int = 768
    top_k_documents: int = 5
    top_k_memories: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def effective_embed_base_url(self) -> str:
        return self.ollama_embed_base_url or self.ollama_base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
