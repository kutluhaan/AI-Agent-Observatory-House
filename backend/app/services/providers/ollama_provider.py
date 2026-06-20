"""
OllamaProvider — local Ollama sunucusu üzerinden BaseLLMProvider implementasyonu.

Ollama OpenAI-compatible endpoint sunuyor (/v1/chat/completions),
bu yüzden httpx ile direkt REST çağrısı yapılır — resmi SDK gerekmez.

Tool calling desteği modele bağlı — bazı local modeller desteklemez.
"""
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.services.providers.base import (
    BaseLLMProvider,
    CompletionResult,
    Message,
    ProviderRequestError,
    StreamEvent,
    ToolDefinition,
)


def _to_ollama_messages(messages: list[Message]) -> list[dict[str, Any]]:
    result = []
    for m in messages:
        entry: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_call_id:
            entry["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            # Ollama uses OpenAI-compatible format for tool calls in assistant messages
            entry["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": (
                            json.loads(tc["arguments"])
                            if isinstance(tc["arguments"], str)
                            else tc["arguments"]
                        ),
                    },
                }
                for tc in m.tool_calls
            ]
        result.append(entry)
    return result


def _to_ollama_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


class OllamaProvider(BaseLLMProvider):
    name = "ollama"
    supports_tools = True  # Model'e bağlı — desteklemeyen modelde tools yok sayılır

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._timeout = 120.0
        # Not: kalıcı bir AsyncClient TUTULMAZ — factory her çağrıda yeni provider
        # üretir ve nesne hiç kapatılmadığı için socket sızardı. Her metot kendi
        # client'ını `async with` ile açıp kapatır.

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": _to_ollama_messages(messages),
                "stream": False,
                "options": {"temperature": temperature},
            }
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens
            if tools:
                payload["tools"] = _to_ollama_tools(tools)

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()

            message = data.get("message", {})
            tool_calls = []
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    tool_calls.append({
                        "id": tc.get("id", ""),
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"]),
                    })

            finish_reason = "tool_calls" if tool_calls else "stop"

            return CompletionResult(
                content=message.get("content", ""),
                finish_reason=finish_reason,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                },
            )

        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(f"Ollama request failed: {e.response.status_code}")
        except httpx.RequestError as e:
            raise ProviderRequestError(f"Ollama unreachable: {str(e)}")

    async def stream(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": _to_ollama_messages(messages),
                "stream": True,
                "options": {"temperature": temperature},
            }
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens
            if tools:
                payload["tools"] = _to_ollama_tools(tools)

            async with httpx.AsyncClient(timeout=self._timeout) as client, client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()

                has_tool_calls = False
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    message = chunk.get("message", {})

                    if message.get("content"):
                        yield StreamEvent(type="token", content=message["content"])

                    if "tool_calls" in message:
                        has_tool_calls = True
                        for tc in message["tool_calls"]:
                            yield StreamEvent(
                                type="tool_call",
                                tool_call={
                                    "id": tc.get("id", ""),
                                    "name": tc["function"]["name"],
                                    "arguments": json.dumps(tc["function"]["arguments"]),
                                },
                            )

                    if chunk.get("done"):
                        finish_reason = "tool_calls" if has_tool_calls else "stop"
                        yield StreamEvent(
                            type="done",
                            finish_reason=finish_reason,
                            usage={
                                "prompt_tokens": chunk.get("prompt_eval_count", 0) or 0,
                                "completion_tokens": chunk.get("eval_count", 0) or 0,
                            },
                        )

        except httpx.HTTPStatusError as e:
            yield StreamEvent(type="error", error_message=f"Ollama request failed: {e.response.status_code}")
        except httpx.RequestError as e:
            yield StreamEvent(type="error", error_message=f"Ollama unreachable: {str(e)}")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
