"""
BaseAgent — tüm agent implementasyonlarının uyduğu sözleşme.

AgentConfig: DB kaydından yüklenen, runner'ı başlatmak için gereken tüm parametreler.
AgentResult: run() çağrısının dönüş tipi.
AgentStreamEvent: stream() generator'ının her yield ettiği event.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AgentConfig:
    agent_id: uuid.UUID
    org_id: uuid.UUID
    name: str
    system_prompt: str
    provider: str
    model: str
    temperature: float
    max_tokens: int | None
    max_steps: int
    timeout_seconds: int
    tool_names: list[str]
    hitl_tool_names: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    content: str
    steps_taken: int
    trace_id: str
    finish_reason: str = "stop"
    total_usage: dict[str, int] = field(default_factory=dict)


@dataclass
class AgentStreamEvent:
    """
    stream() generator'ının yield ettiği her event.

    Tipler:
      token           — LLM'den gelen metin parçası
      tool_call_start — tool çalışmaya başladı
      tool_call_end   — tool sonuçlandı
      hitl_requested  — insan onayı bekleniyor (tool çağrısı askıya alındı)
      hitl_resolved   — insan kararı geldi (approved/modified/rejected)
      step_done       — bir adım (LLM turu) tamamlandı
      done            — tüm çalıştırma bitti
      error           — kurtarılamaz hata
    """
    type: Literal[
        "token", "tool_call_start", "tool_call_end",
        "hitl_requested", "hitl_resolved",
        "step_done", "done", "error",
    ]
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: str | None = None
    step: int | None = None
    finish_reason: str | None = None
    trace_id: str | None = None
    steps_taken: int | None = None
    total_usage: dict[str, int] | None = None
    error_code: str | None = None
    error_message: str | None = None
    # HITL fields
    hitl_request_id: str | None = None
    hitl_action: str | None = None        # approved | modified | rejected
    hitl_modified_arguments: dict[str, Any] | None = None

    def to_sse(self) -> str:
        """
        Server-Sent Events formatında string döner.
        Boş content alanları payload'a dahil edilmez.
        """
        import json
        payload: dict[str, Any] = {}
        for key in (
            "content", "tool_name", "tool_arguments", "tool_result",
            "step", "finish_reason", "trace_id", "steps_taken",
            "total_usage", "error_code", "error_message",
        ):
            val = getattr(self, key)
            if val is not None:
                payload[key] = val
        for key in ("hitl_request_id", "hitl_action", "hitl_modified_arguments"):
            val = getattr(self, key)
            if val is not None:
                payload[key] = val
        return f"event: {self.type}\ndata: {json.dumps(payload)}\n\n"


# ─── Hata Sınıfları ───────────────────────────────────────

class AgentError(Exception):
    code: str = "AGENT_ERROR"
    status_code: int = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AgentMaxStepsError(AgentError):
    code = "AGENT_MAX_STEPS_EXCEEDED"
    status_code = 422

    def __init__(self, max_steps: int):
        super().__init__(f"Agent reached the maximum step limit ({max_steps}).")


class AgentTimeoutError(AgentError):
    code = "AGENT_TIMEOUT"
    status_code = 408

    def __init__(self, timeout: int):
        super().__init__(f"Agent execution timed out after {timeout} seconds.")


class AgentToolError(AgentError):
    code = "AGENT_TOOL_ERROR"
    status_code = 502


class HITLRejectedError(AgentError):
    code = "HITL_REJECTED"
    status_code = 422

    def __init__(self, tool_name: str, reason: str = ""):
        msg = f"Human rejected tool call '{tool_name}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


class HITLTimeoutError(AgentError):
    code = "HITL_TIMEOUT"
    status_code = 408

    def __init__(self, request_id: str):
        super().__init__(f"HITL request '{request_id}' timed out — no human response within 10 minutes.")


# ─── Abstract Base ────────────────────────────────────────

class BaseAgent(ABC):
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    @abstractmethod
    async def run(self, user_input: str) -> AgentResult:
        """Blocking — tüm çalıştırma tamamlanana kadar bekler."""
        ...

    @abstractmethod
    async def stream(self, user_input: str) -> AsyncIterator[AgentStreamEvent]:
        """SSE için token-by-token async generator."""
        ...
