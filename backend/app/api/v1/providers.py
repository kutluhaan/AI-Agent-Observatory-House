"""
Providers Router — M7

Endpoint'ler:
  POST   /providers              — org'a provider key ekle/güncelle (admin)
  GET    /providers               — org'un yapılandırılı provider'larını listele (member)
  DELETE /providers/{provider}    — provider credential sil (admin)
  GET    /providers/{provider}/health — provider'a test çağrısı (member)
  POST   /providers/{provider}/test-completion — gerçek completion + trace (member, M8)
"""
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.encryption import encrypt_value
from app.core.redis import get_redis
from app.core.responses import AppError, ForbiddenError, NotFoundError, success
from app.models.provider import ProviderCredential
from app.schemas.providers import SetProviderCredentialRequest
from app.schemas.traces import TestCompletionRequest
from app.services.providers.base import Message, ProviderError
from app.services.providers.factory import SUPPORTED_PROVIDERS, get_provider
from app.services.trace_collector import Tracer

router = APIRouter()


def _mask_key(plain_hint_len: int = 4) -> str:
    """Key'in son N karakteri DB'de tutulmaz — bu yüzden sabit maske döneriz."""
    return "•" * 20


@router.post("", status_code=201)
async def set_provider_credential(
    body: SetProviderCredentialRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    """
    Org için provider credential ekler/günceller.
    Ollama: base_url zorunlu, api_key opsiyonel.
    OpenAI/Anthropic: api_key zorunlu.
    """
    if body.provider == "ollama":
        if not body.base_url:
            raise AppError("VALIDATION_ERROR", "base_url is required for Ollama.", 422)
    else:
        if not body.api_key:
            raise AppError("VALIDATION_ERROR", "api_key is required for this provider.", 422)

    result = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == ctx.org_id,
            ProviderCredential.provider == body.provider,
        )
    )
    credential = result.scalar_one_or_none()

    encrypted = encrypt_value(body.api_key) if body.api_key else None

    if credential:
        credential.encrypted_key = encrypted
        credential.base_url = body.base_url
        credential.is_active = True
        credential.updated_at = datetime.now(UTC)
    else:
        credential = ProviderCredential(
            organization_id=ctx.org_id,
            provider=body.provider,
            encrypted_key=encrypted,
            base_url=body.base_url,
            is_active=True,
        )
        db.add(credential)

    await db.commit()

    return success({
        "provider": credential.provider,
        "is_configured": True,
        "base_url": credential.base_url,
    })


@router.get("")
async def list_provider_credentials(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Org'un yapılandırılı provider'larını listeler. Key'ler maskeli döner."""
    result = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == ctx.org_id,
        )
    )
    credentials = {c.provider: c for c in result.scalars().all()}

    return success([
        {
            "provider": p,
            "is_configured": p in credentials and credentials[p].is_active,
            "masked_key": _mask_key() if p in credentials and credentials[p].encrypted_key else None,
            "base_url": credentials[p].base_url if p in credentials else None,
            "updated_at": credentials[p].updated_at.isoformat() if p in credentials else None,
        }
        for p in sorted(SUPPORTED_PROVIDERS)
    ])


@router.delete("/{provider}", status_code=204)
async def delete_provider_credential(
    provider: str,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    """Provider credential'ı siler — org platform fallback'e döner."""
    result = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == ctx.org_id,
            ProviderCredential.provider == provider,
        )
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise NotFoundError("PROVIDER_NOT_CONFIGURED", "No credential configured for this provider.")

    await db.delete(credential)
    await db.commit()


@router.get("/{provider}/health")
async def check_provider_health(
    provider: str,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Provider'a minimal test çağrısı yapar."""
    instance = await get_provider(db, ctx.org_id, provider)
    healthy = await instance.health_check()

    return success({
        "provider": provider,
        "healthy": healthy,
    })


@router.post("/{provider}/test-completion")
async def test_completion(
    provider: str,
    body: TestCompletionRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("member")),
):
    """
    Gerçek bir completion çalıştırır ve adımlarını trace eder (M8 doğrulama seam'i).

    Olay akışı: agent_start → llm_call_start → llm_call_end → agent_end.
    M9'daki Agent Engine bu seam'i gerçek execution loop'una genişletecek.
    """
    instance = await get_provider(db, ctx.org_id, provider)

    tracer = Tracer(redis, organization_id=str(ctx.org_id), name=f"test-completion:{provider}")
    await tracer.start()

    messages: list[Message] = []
    if body.system:
        messages.append(Message(role="system", content=body.system))
    messages.append(Message(role="user", content=body.prompt))

    await tracer.event("llm_call_start", {"provider": provider, "model": body.model})

    try:
        result = await instance.complete(messages, model=body.model)
    except ProviderError as exc:
        await tracer.event("error", {"code": exc.code, "message": exc.message})
        await tracer.end(status="error", payload={"error_code": exc.code})
        raise AppError(exc.code, exc.message, exc.status_code)

    await tracer.event(
        "llm_call_end",
        {"model": body.model, "finish_reason": result.finish_reason, "usage": result.usage},
    )
    await tracer.end(status="completed", payload={"finish_reason": result.finish_reason})

    return success({
        "trace_id": tracer.trace_id,
        "content": result.content,
        "finish_reason": result.finish_reason,
        "usage": result.usage,
    })
