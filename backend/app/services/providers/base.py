"""
BaseLLMProvider — tüm provider'ların uyduğu tek interface.

Tasarım kararı: M9'daki Agent Engine hangi provider kullanıldığını bilmemeli.
Bu yüzden hem request hem response formatı normalize edilir.

Streaming format (her provider stream() metodunda bu event'leri üretir):
  {"type": "token", "content": "..."}
  {"type": "tool_call", "id": "...", "name": "...", "arguments": {...}}
  {"type": "done", "finish_reason": "stop" | "tool_calls" | "length"}
  {"type": "error", "message": "..."}
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal


# ─── Normalize Edilmiş Tipler ─────────────────────────────

@dataclass
class ToolDefinition:
    """Provider'a bağımsız tool tanımı. Her provider kendi formatına çevirir."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class Message:
    """Provider'a bağımsız mesaj formatı."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None  # role=tool ise hangi çağrıya cevap
    tool_calls: list[dict[str, Any]] | None = None  # role=assistant ise yaptığı çağrılar


@dataclass
class CompletionResult:
    """Non-streaming complete() çağrısının sonucu."""
    content: str
    finish_reason: Literal["stop", "tool_calls", "length", "error"]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens


@dataclass
class StreamEvent:
    """stream() async generator'ının her yield ettiği event."""
    type: Literal["token", "tool_call", "done", "error"]
    content: str | None = None
    tool_call: dict[str, Any] | None = None
    finish_reason: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_call is not None:
            result["tool_call"] = self.tool_call
        if self.finish_reason is not None:
            result["finish_reason"] = self.finish_reason
        if self.error_message is not None:
            result["message"] = self.error_message
        return result


# ─── Provider Hataları ────────────────────────────────────

class ProviderError(Exception):
    """Tüm provider hataları için temel sınıf."""
    def __init__(self, code: str, message: str, status_code: int = 502):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProviderAuthError(ProviderError):
    def __init__(self, message: str = "Provider API key is invalid."):
        super().__init__("PROVIDER_AUTH_FAILED", message, 401)


class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str = "Provider rate limit exceeded."):
        super().__init__("PROVIDER_RATE_LIMITED", message, 429)


class ProviderRequestError(ProviderError):
    def __init__(self, message: str = "Provider request failed."):
        super().__init__("PROVIDER_REQUEST_FAILED", message, 502)


# ─── Base Interface ────────────────────────────────────────

class BaseLLMProvider(ABC):
    """
    Her provider bu sınıfı implement eder.
    Factory bu interface üzerinden döner — çağıran kod hangi provider olduğunu bilmez.
    """

    name: str  # "openai" | "anthropic" | "ollama"
    supports_tools: bool = True

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Non-streaming tek cevap döner."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Token'ları normalize StreamEvent olarak yield eder."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Provider'a minimal bir test çağrısı yapar. Erişilebilirse True."""
        ...
