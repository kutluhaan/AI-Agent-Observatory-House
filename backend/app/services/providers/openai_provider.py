"""
OpenAIProvider — OpenAI Chat Completions API üzerinden BaseLLMProvider implementasyonu.
"""
import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, AuthenticationError, RateLimitError as OpenAIRateLimitError, APIError

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


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    result = []
    for m in messages:
        entry: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_call_id:
            entry["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            # OpenAI expects {id, type, function: {name, arguments}} — not our internal {id, name, arguments}
            entry["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": (
                            tc["arguments"]
                            if isinstance(tc["arguments"], str)
                            else json.dumps(tc["arguments"])
                        ),
                    },
                }
                for tc in m.tool_calls
            ]
        result.append(entry)
    return result


def _to_openai_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
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


class OpenAIProvider(BaseLLMProvider):
    name = "openai"
    supports_tools = True

    def __init__(self, api_key: str):
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": _to_openai_messages(messages),
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            if tools:
                kwargs["tools"] = _to_openai_tools(tools)

            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]

            tool_calls = []
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in choice.message.tool_calls
                ]

            finish_reason = choice.finish_reason
            normalized_reason = "tool_calls" if finish_reason == "tool_calls" else (
                "length" if finish_reason == "length" else "stop"
            )

            return CompletionResult(
                content=choice.message.content or "",
                finish_reason=normalized_reason,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )

        except AuthenticationError as e:
            raise ProviderAuthError(str(e))
        except OpenAIRateLimitError as e:
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
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": _to_openai_messages(messages),
                "temperature": temperature,
                "stream": True,
                "stream_options": {"include_usage": True},  # final chunk'ta usage gelsin
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            if tools:
                kwargs["tools"] = _to_openai_tools(tools)

            stream = await self._client.chat.completions.create(**kwargs)

            # OpenAI sends tool call arguments across many delta chunks indexed by `index`.
            # Accumulate here; yield complete tool_call events when finish_reason arrives.
            tool_calls_buf: dict[int, dict[str, Any]] = {}
            usage: dict[str, int] | None = None
            pending_finish: str | None = None

            async for chunk in stream:
                # usage chunk (choices boş) finish_reason chunk'ından SONRA gelir
                if getattr(chunk, "usage", None):
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                    }
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                if delta.content:
                    yield StreamEvent(type="token", content=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_buf[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_buf[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_buf[idx]["arguments"] += tc.function.arguments

                if finish_reason:
                    for tc_data in tool_calls_buf.values():
                        yield StreamEvent(type="tool_call", tool_call=tc_data)
                    pending_finish = "tool_calls" if finish_reason == "tool_calls" else (
                        "length" if finish_reason == "length" else "stop"
                    )

            # done'u stream bitince yay — usage chunk'ı yakaladıktan sonra
            if pending_finish is not None:
                yield StreamEvent(type="done", finish_reason=pending_finish, usage=usage)

        except AuthenticationError as e:
            yield StreamEvent(type="error", error_message=str(e))
        except OpenAIRateLimitError as e:
            yield StreamEvent(type="error", error_message=str(e))
        except APIError as e:
            yield StreamEvent(type="error", error_message=str(e))

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
