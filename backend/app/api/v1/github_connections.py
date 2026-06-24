"""
GitHub Connections Router — GitHub (loop it.9)

Org-bazlı GitHub PAT. Token şifreli saklanır, ham dönmez.

  POST   /github-connections            — ekle (admin)
  GET    /github-connections            — listele (member)
  DELETE /github-connections/{id}       — sil (admin)
  POST   /github-connections/{id}/test  — token'ı doğrula (GET /user) (member)
"""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.encryption import decrypt_value, encrypt_value
from app.core.responses import AppError, NotFoundError, success
from app.models.github_connection import GithubConnection
from app.services.agent.tools.github import _gh

router = APIRouter()


class CreateGithubConnRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    token: Annotated[str, Field(min_length=8, max_length=500)]


class GithubConnResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, c: Any) -> "GithubConnResponse":
        return cls(id=c.id, name=c.name, is_active=c.is_active, created_at=c.created_at.isoformat())


async def _get_or_404(cid: uuid.UUID, org_id, db: AsyncSession) -> GithubConnection:
    row = (await db.execute(
        select(GithubConnection).where(GithubConnection.id == cid, GithubConnection.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("GITHUB_CONNECTION_NOT_FOUND", "GitHub connection not found.")
    return row


@router.post("", status_code=201)
async def create_github_conn(body: CreateGithubConnRequest, db: AsyncSession = Depends(get_db),
                             ctx: TenantContext = Depends(require_role("admin"))):
    dup = (await db.execute(select(GithubConnection).where(
        GithubConnection.organization_id == ctx.org_id, GithubConnection.name == body.name))).scalar_one_or_none()
    if dup:
        raise AppError("GITHUB_CONN_NAME_CONFLICT", f"A connection named '{body.name}' already exists.", 409)
    c = GithubConnection(id=uuid.uuid4(), organization_id=ctx.org_id, name=body.name,
                         encrypted_token=encrypt_value(body.token))
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return success(GithubConnResponse.from_orm(c).model_dump())


@router.get("")
async def list_github_conns(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    rows = (await db.execute(select(GithubConnection).where(
        GithubConnection.organization_id == ctx.org_id).order_by(GithubConnection.created_at.desc()))).scalars().all()
    return success([GithubConnResponse.from_orm(c).model_dump() for c in rows])


@router.delete("/{conn_id}", status_code=204)
async def delete_github_conn(conn_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                             ctx: TenantContext = Depends(require_role("admin"))):
    c = await _get_or_404(conn_id, ctx.org_id, db)
    await db.delete(c)
    await db.commit()


@router.post("/{conn_id}/test")
async def test_github_conn(conn_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                           ctx: TenantContext = Depends(require_role("member"))):
    c = await _get_or_404(conn_id, ctx.org_id, db)
    status, data = await _gh(decrypt_value(c.encrypted_token), "/user")
    if status != 200 or not isinstance(data, dict):
        raise AppError("GITHUB_CONN_TEST_FAILED", f"Token invalid ({status})", 502)
    return success({"ok": True, "login": data.get("login")})
