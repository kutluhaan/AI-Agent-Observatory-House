"""Provider Pydantic Schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class SetProviderCredentialRequest(BaseModel):
    provider: str
    api_key: str | None = None   # ollama/custom'da opsiyonel
    base_url: str | None = None  # ollama ve custom (OpenAI-uyumlu) için

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("openai", "anthropic", "gemini", "ollama", "custom"):
            raise ValueError("Provider must be openai, anthropic, gemini, ollama, or custom.")
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
