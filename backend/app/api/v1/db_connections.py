"""
Database Connections Router — Veritabanı & SQL (loop it.8)

Org-bazlı dış PostgreSQL bağlantısı. DSN şifreli saklanır, ham dönmez.

  POST   /db-connections            — ekle (admin)
  GET    /db-connections            — listele (member)
  DELETE /db-connections/{id}       — sil (admin)
  POST   /db-connections/{id}/test  — bağlantıyı test et (member)
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
from app.models.db_connection import DbConnection
from app.services.agent.tools.sql import _run_readonly

router = APIRouter()


class CreateDbConnRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    dsn: Annotated[str, Field(min_length=10, max_length=2000)]  # postgresql://user:pass@host:port/db


class DbConnResponse(BaseModel):
    id: uuid.UUID
    name: str
    db_type: str
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, c: Any) -> "DbConnResponse":
        return cls(id=c.id, name=c.name, db_type=c.db_type, is_active=c.is_active, created_at=c.created_at.isoformat())


async def _get_or_404(cid: uuid.UUID, org_id, db: AsyncSession) -> DbConnection:
    row = (await db.execute(
        select(DbConnection).where(DbConnection.id == cid, DbConnection.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("DB_CONNECTION_NOT_FOUND", "Database connection not found.")
    return row


@router.post("", status_code=201)
async def create_db_conn(body: CreateDbConnRequest, db: AsyncSession = Depends(get_db),
                         ctx: TenantContext = Depends(require_role("admin"))):
    dup = (await db.execute(select(DbConnection).where(
        DbConnection.organization_id == ctx.org_id, DbConnection.name == body.name))).scalar_one_or_none()
    if dup:
        raise AppError("DB_CONN_NAME_CONFLICT", f"A connection named '{body.name}' already exists.", 409)
    c = DbConnection(id=uuid.uuid4(), organization_id=ctx.org_id, name=body.name,
                     db_type="postgres", encrypted_dsn=encrypt_value(body.dsn))
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return success(DbConnResponse.from_orm(c).model_dump())


@router.get("")
async def list_db_conns(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    rows = (await db.execute(select(DbConnection).where(
        DbConnection.organization_id == ctx.org_id).order_by(DbConnection.created_at.desc()))).scalars().all()
    return success([DbConnResponse.from_orm(c).model_dump() for c in rows])


@router.delete("/{conn_id}", status_code=204)
async def delete_db_conn(conn_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         ctx: TenantContext = Depends(require_role("admin"))):
    c = await _get_or_404(conn_id, ctx.org_id, db)
    await db.delete(c)
    await db.commit()


@router.post("/{conn_id}/test")
async def test_db_conn(conn_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       ctx: TenantContext = Depends(require_role("member"))):
    c = await _get_or_404(conn_id, ctx.org_id, db)
    try:
        await _run_readonly(decrypt_value(c.encrypted_dsn), "SELECT 1 AS ok", max_rows=1)
    except Exception as exc:  # noqa: BLE001
        raise AppError("DB_CONN_TEST_FAILED", f"Connection failed: {exc}", 502)
    return success({"ok": True})
