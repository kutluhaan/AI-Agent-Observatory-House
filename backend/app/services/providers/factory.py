"""
Provider Factory — org_id + provider adına göre doğru BaseLLMProvider instance'ını döner.

Key çözümleme sırası:
  1. Org'un kendi credential'ı varsa (provider_credentials tablosu) → şifre çözülüp kullanılır
  2. Yoksa platform-level .env key'ine fallback yapılır
  3. Hiçbiri yoksa PROVIDER_NOT_CONFIGURED hatası

Ollama özel durum: base_url her zaman gerekli, org override edebilir, yoksa .env'deki kullanılır.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt_value
from app.core.responses import AppError
from app.models.provider import ProviderCredential
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.base import BaseLLMProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_provider import OpenAIProvider

settings = get_settings()

SUPPORTED_PROVIDERS = {"openai", "anthropic", "ollama"}


async def get_provider(
    db: AsyncSession,
    org_id: uuid.UUID,
    provider_name: str,
) -> BaseLLMProvider:
    """
    Org için yapılandırılmış provider instance'ı döner.

    Raises:
        AppError(PROVIDER_NOT_SUPPORTED, 422): geçersiz provider adı
        AppError(PROVIDER_NOT_CONFIGURED, 404): org ve platform'da key yok
    """
    if provider_name not in SUPPORTED_PROVIDERS:
        raise AppError(
            "PROVIDER_NOT_SUPPORTED",
            f"Provider '{provider_name}' is not supported. Supported: {', '.join(SUPPORTED_PROVIDERS)}.",
            422,
        )

    # Org'un kendi credential'ını ara
    result = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == org_id,
            ProviderCredential.provider == provider_name,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    )
    credential = result.scalar_one_or_none()

    if provider_name == "ollama":
        base_url = (credential.base_url if credential else None) or settings.ollama_base_url
        if not base_url:
            raise AppError(
                "PROVIDER_NOT_CONFIGURED",
                "Ollama base URL is not configured for this organization or platform.",
                404,
            )
        return OllamaProvider(base_url=base_url)

    # openai / anthropic — API key gerekli
    api_key: str | None = None
    if credential and credential.encrypted_key:
        api_key = decrypt_value(credential.encrypted_key)
    else:
        api_key = (
            settings.openai_api_key if provider_name == "openai" else settings.anthropic_api_key
        )

    if not api_key:
        raise AppError(
            "PROVIDER_NOT_CONFIGURED",
            f"No API key configured for '{provider_name}' — neither organization nor platform level.",
            404,
        )

    if provider_name == "openai":
        return OpenAIProvider(api_key=api_key)
    return AnthropicProvider(api_key=api_key)
