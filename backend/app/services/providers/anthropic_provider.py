"""
AnthropicProvider — Anthropic Messages API üzerinden BaseLLMProvider implementasyonu.

Anthropic'in farkı: system message ayrı parametre, content blocks farklı yapıda.
"""
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic, AuthenticationError, RateLimitError as AnthropicRateLimitError, APIError

from app.services.providers.base import (
    BaseLLMProvider,
    CompletionResult,
    Message,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    StreamEvent,
    ToolDefinition,
)


def _split_system_and_messages(messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
    """Anthropic'te system mesajı ayrı parametre — messages listesinden çıkarılır."""
    system_parts = [m.content for m in messages if m.role == "system"]
    system = "\n".join(system_parts) if system_parts else ""

    chat_messages = []
    for m in messages:
        if m.role == "system":
            continue
        if m.role == "tool":
            chat_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                }],
            })
        else:
            chat_messages.append({"role": m.role, "content": m.content})

    return system, chat_messages


def _to_anthropic_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    supports_tools = True

    def __init__(self, api_key: str):
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        try:
            system, chat_messages = _split_system_and_messages(messages)
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": chat_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            if system:
                kwargs["system"] = system
            if tools:
                kwargs["tools"] = _to_anthropic_tools(tools)

            response = await self._client.messages.create(**kwargs)

            text_content = ""
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    })

            normalized_reason = "tool_calls" if response.stop_reason == "tool_use" else (
                "length" if response.stop_reason == "max_tokens" else "stop"
            )

            return CompletionResult(
                content=text_content,
                finish_reason=normalized_reason,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
            )

        except AuthenticationError as e:
            raise ProviderAuthError(str(e))
        except AnthropicRateLimitError as e:
            raise ProviderRateLimitError(str(e))
        except APIError as e:
            raise ProviderRequestError(str(e))

    async def stream(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        try:
            system, chat_messages = _split_system_and_messages(messages)
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": chat_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            if system:
                kwargs["system"] = system
            if tools:
                kwargs["tools"] = _to_anthropic_tools(tools)

            async with self._client.messages.stream(**kwargs) as stream:
                current_tool_call: dict[str, Any] | None = None

                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool_call = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "arguments": "",
                            }

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield StreamEvent(type="token", content=event.delta.text)
                        elif event.delta.type == "input_json_delta" and current_tool_call:
                            current_tool_call["arguments"] += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool_call:
                            yield StreamEvent(type="tool_call", tool_call=current_tool_call)
                            current_tool_call = None

                    elif event.type == "message_delta":
                        stop_reason = event.delta.stop_reason
                        if stop_reason:
                            normalized = "tool_calls" if stop_reason == "tool_use" else (
                                "length" if stop_reason == "max_tokens" else "stop"
                            )
                            yield StreamEvent(type="done", finish_reason=normalized)

        except AuthenticationError as e:
            yield StreamEvent(type="error", error_message=str(e))
        except AnthropicRateLimitError as e:
            yield StreamEvent(type="error", error_message=str(e))
        except APIError as e:
            yield StreamEvent(type="error", error_message=str(e))

    async def health_check(self) -> bool:
        try:
            await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
