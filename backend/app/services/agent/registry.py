"""
ToolRegistry — agent'ların kullanabileceği araçların merkezi kaydı.

Her tool kodda tanımlanır ve ToolRegistry.register() ile kaydedilir.
Agent DB kaydı sadece tool isimlerini saklar; runner çalışma zamanında
isimleri somut handler'lara çözümler.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.providers.base import ToolDefinition


@dataclass
class ToolContext:
    """
    Tool handler'larına inject edilen çalışma zamanı context'i.
    DB erişimi gerektiren tool'lar (call_agent, file tool'ları) bunu kullanır.
    agent_id: izole dosya sistemi tool'ları için — hangi agent'ın FS'i.
    """
    org_id: uuid.UUID
    trace_id: str
    db: Any  # AsyncSession — circular import'u önlemek için Any
    redis: Any  # aioredis.Redis
    agent_id: uuid.UUID | None = None
    # G1: kullanıcı bağlamı — Gmail gibi per-user OAuth tool'ları doğru bağlantıyı seçmek için kullanır
    user_id: uuid.UUID | None = None
    # F8: ekip bağlamı — team tool'ları (delegate/team_share/team_board) bunu kullanır
    team_id: uuid.UUID | None = None
    team_run_id: uuid.UUID | None = None
    current_role: str | None = None


@dataclass
class ToolHandler:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object
    handler: Callable  # async (ctx: ToolContext, **kwargs) -> str


class ToolRegistry:
    _tools: dict[str, ToolHandler] = {}

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        parameters: dict[str, Any],
    ) -> Callable:
        """
        Dekoratör factory.

        Kullanım:
            @ToolRegistry.register("echo", "Girdiyi döner", {...schema...})
            async def echo_handler(ctx: ToolContext, text: str) -> str:
                return text
        """
        def decorator(fn: Callable) -> Callable:
            if name in cls._tools:
                raise ValueError(f"Tool '{name}' zaten kayıtlı.")
            cls._tools[name] = ToolHandler(
                name=name,
                description=description,
                parameters=parameters,
                handler=fn,
            )
            return fn
        return decorator

    @classmethod
    def get(cls, name: str) -> ToolHandler:
        if name not in cls._tools:
            raise KeyError(f"Tool '{name}' kayıtlı değil.")
        return cls._tools[name]

    @classmethod
    def build_definitions(cls, names: list[str]) -> list[ToolDefinition]:
        """Provider'a gönderilecek ToolDefinition listesini oluşturur."""
        defs: list[ToolDefinition] = []
        for name in names:
            handler = cls.get(name)
            defs.append(ToolDefinition(
                name=handler.name,
                description=handler.description,
                parameters=handler.parameters,
            ))
        return defs

    @classmethod
    def all_names(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    def _reset(cls) -> None:
        """Sadece testlerde kullanılır."""
        cls._tools = {}
