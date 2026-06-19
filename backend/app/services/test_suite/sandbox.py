"""
AgentSandbox — M11

AgentRunner'ı izole test ortamında çalıştırır.
Synthetic geçmiş (history) inject ederek belirli senaryoları simüle eder.

Kullanım:
    sandbox = AgentSandbox(config, provider, redis)
    result = await sandbox.run(
        user_input="Merhaba",
        history=[
            {"role": "user", "content": "Önceki soru"},
            {"role": "assistant", "content": "Önceki yanıt"},
        ],
    )
    # result.agent_result, result.latency_ms, result.tools_called
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.services.agent.base import AgentConfig, AgentResult
from app.services.agent.registry import ToolContext
from app.services.agent.runner import AgentRunner
from app.services.providers.base import BaseLLMProvider, Message
from app.services.test_suite.assertions import SandboxResult
from app.services.trace_collector import Tracer


class AgentSandbox:
    """
    Test için izole AgentRunner wrapper'ı.

    tools_called: Runner tamamlandıktan sonra hangi tool'ların çağrıldığını
    trace event'lerinden çıkarmak yerine, runner'ı patch ederek izler.
    """

    def __init__(
        self,
        config: AgentConfig,
        provider: BaseLLMProvider,
        redis: aioredis.Redis,
        db: Any | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.redis = redis
        self.db = db

    async def run(
        self,
        user_input: str,
        history: list[dict[str, str]] | None = None,
    ) -> SandboxResult:
        """
        Agent'ı çalıştırır ve SandboxResult döner.

        Args:
            user_input: Kullanıcı girdisi.
            history: Synthetic message history — [{"role": ..., "content": ...}]
                     Sohbet geçmişini simüle etmek için inject edilir.
        """
        tracer = Tracer(
            redis=self.redis,
            organization_id=str(self.config.org_id),
            name=f"sandbox:{self.config.name}",
        )

        tool_context = ToolContext(
            org_id=self.config.org_id,
            trace_id=tracer.trace_id,
            db=self.db,
            redis=self.redis,
        )

        runner = _InstrumentedRunner(
            config=self.config,
            provider=self.provider,
            tracer=tracer,
            tool_context=tool_context,
        )

        # Synthetic history inject et
        if history:
            for msg in history:
                runner._inject_history(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                )

        start = time.monotonic()
        agent_result: AgentResult = await runner.run(user_input)
        latency_ms = int((time.monotonic() - start) * 1000)

        return SandboxResult(
            agent_result=agent_result,
            latency_ms=latency_ms,
            tools_called=runner.tools_called,
        )


class _InstrumentedRunner(AgentRunner):
    """
    AgentRunner'ı tool call'ları izlemek için genişletir.
    Standart runner API'sini korur — sadece tools_called listesi eklenir.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tools_called: list[str] = []
        self._history_prefix: list[Message] = []

    def _inject_history(self, role: str, content: str) -> None:
        """Çalıştırmadan önce mesaj geçmişine ekle."""
        self._history_prefix.append(Message(role=role, content=content))

    def _build_messages(self, user_input: str) -> list[Message]:
        """
        Üst sınıfın sistem mesajı + user_input yapısının başına
        synthetic geçmişi ekle.
        """
        base = super()._build_messages(user_input)
        if not self._history_prefix:
            return base
        has_system = bool(self.config.system_prompt)
        if has_system:
            # base = [system_msg, user_msg]
            return [base[0]] + self._history_prefix + [base[-1]]
        else:
            # base = [user_msg]
            return self._history_prefix + base

    async def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        result = await super()._execute_tool(tool_name, arguments)
        self.tools_called.append(tool_name)
        return result
