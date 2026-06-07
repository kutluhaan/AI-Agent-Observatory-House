"""
Alembic async migration environment.

Bu dosya 'alembic upgrade head' komutu çalıştırıldığında devreye girer.
DATABASE_URL environment variable'ından bağlantı bilgisini okur.

Neden async? Backend'in tamamı async (asyncpg) kullanıyor.
Alembic'in sync mode'u ayrı bir sync engine gerektirir — tutarsızlık yaratır.
Async mode ile tek engine, tutarlı yapı.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Tüm modelleri import et — Base.metadata'nın tüm tabloları tanıması için şart
from app.core.database import Base
import app.models  # noqa: F401 — side effect import, modelleri Base'e kaydeder

config = context.config

# DATABASE_URL'i environment'tan al — alembic.ini'deki placeholder'ı override et
database_url = os.getenv("DATABASE_URL", "")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Offline mode: DB bağlantısı olmadan SQL script üretir.
    Kullanım: CI/CD'de migration script'i önceden üretmek için.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Kolon tip değişikliklerini tespit et
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online async mode: gerçek DB'ye bağlanarak migration'ları uygular."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Migration sırasında connection pool gerekmez
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
