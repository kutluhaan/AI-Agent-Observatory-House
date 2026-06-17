"""Provider Pydantic Schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class SetProviderCredentialRequest(BaseModel):
    provider: str
    api_key: str | None = None  # ollama'da gerekmez
    base_url: str | None = None  # sadece ollama'da kullanılır

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("openai", "anthropic", "ollama"):
            raise ValueError("Provider must be 'openai', 'anthropic', or 'ollama'.")
        return v


class ProviderCredentialResponse(BaseModel):
    provider: str
    is_configured: bool
    masked_key: str | None = None  # "sk-...AbCd" formatında
    base_url: str | None = None
    updated_at: datetime | None = None


class ProviderHealthResponse(BaseModel):
    provider: str
    healthy: bool
