"""
GeminiProvider — Google Gemini API üzerinden BaseLLMProvider implementasyonu.

Yeni birleşik SDK kullanılır: `from google import genai` (google-genai).
Anthropic gibi: system mesajı ayrı (config.system_instruction), roller user/model,
tool sonuçları function_response part'ı olarak gider.
"""
from collections.abc import AsyncIterator
from typing import Any

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


def _split_system_and_contents(messages: list[Message]) -> tuple[str | None, list[Any]]:
    """Gemini: system ayrı parametre; mesajlar Content(role=user|model, parts=[...])."""
    from google.genai import types

    system_parts = [m.content for m in messages if m.role == "system"]
    system = "\n".join(p for p in system_parts if p) or None

    contents: list[Any] = []
    for m in messages:
        if m.role == "system":
            continue
        if m.role == "assistant":
            parts: list[Any] = []
            if m.content:
                parts.append(types.Part(text=m.content))
            for tc in m.tool_calls or []:
                args = tc.get("arguments", {})
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = {}
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(name=tc.get("name", ""), args=args or {})
                    )
                )
            contents.append(types.Content(role="model", parts=parts or [types.Part(text="")]))
        elif m.role == "tool":
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=m.tool_call_id or "",
                                response={"result": m.content},
                            )
                        )
                    ],
                )
            )
        else:  # user
            contents.append(types.Content(role="user", parts=[types.Part(text=m.content)]))

    return system, contents


def _to_gemini_tools(tools: list[ToolDefinition]) -> list[Any]:
    from google.genai import types

    declarations = [
        types.FunctionDeclaration(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in tools
    ]
    return [types.Tool(function_declarations=declarations)]


def _build_config(
    system: str | None,
    temperature: float,
    max_tokens: int | None,
    tools: list[ToolDefinition] | None,
) -> Any:
    from google.genai import types

    kwargs: dict[str, Any] = {"temperature": temperature}
    if system:
        kwargs["system_instruction"] = system
    if max_tokens:
        kwargs["max_output_tokens"] = max_tokens
    if tools:
        kwargs["tools"] = _to_gemini_tools(tools)
    return types.GenerateContentConfig(**kwargs)


def _normalize_finish(finish_reason: Any, has_tool_calls: bool) -> str:
    if has_tool_calls:
        return "tool_calls"
    name = getattr(finish_reason, "name", str(finish_reason or "")).upper()
    if name == "MAX_TOKENS":
        return "length"
    return "stop"


def _raise_mapped(exc: Exception) -> None:
    """google-genai APIError → normalize edilmiş provider hatası."""
    code = getattr(exc, "code", None)
    if code in (401, 403):
        raise ProviderAuthError(str(exc))
    if code == 429:
        raise ProviderRateLimitError(str(exc))
    raise ProviderRequestError(str(exc))


class GeminiProvider(BaseLLMProvider):
    name = "gemini"
    supports_tools = True

    def __init__(self, api_key: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        from google.genai import errors

        try:
            system, contents = _split_system_and_contents(messages)
            config = _build_config(system, temperature, max_tokens, tools)

            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            text_content = ""
            tool_calls: list[dict[str, Any]] = []
            candidate = response.candidates[0] if response.candidates else None
            if candidate and candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if getattr(part, "text", None):
                        text_content += part.text
                    fc = getattr(part, "function_call", None)
                    if fc is not None:
                        tool_calls.append({
                            "id": fc.name,
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {},
                        })

            finish = candidate.finish_reason if candidate else None
            usage_meta = getattr(response, "usage_metadata", None)

            return CompletionResult(
                content=text_content,
                finish_reason=_normalize_finish(finish, bool(tool_calls)),
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
                    "completion_tokens": getattr(usage_meta, "candidates_token_count", 0) or 0,
                },
            )
        except errors.APIError as exc:
            _raise_mapped(exc)

    async def stream(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        from google.genai import errors

        try:
            system, contents = _split_system_and_contents(messages)
            config = _build_config(system, temperature, max_tokens, tools)

            has_tool_calls = False
            usage: dict[str, int] | None = None
            stream = await self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                um = getattr(chunk, "usage_metadata", None)
                if um is not None:
                    usage = {
                        "prompt_tokens": getattr(um, "prompt_token_count", 0) or 0,
                        "completion_tokens": getattr(um, "candidates_token_count", 0) or 0,
                    }
                candidate = chunk.candidates[0] if chunk.candidates else None
                if candidate and candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if getattr(part, "text", None):
                            yield StreamEvent(type="token", content=part.text)
                        fc = getattr(part, "function_call", None)
                        if fc is not None:
                            has_tool_calls = True
                            yield StreamEvent(
                                type="tool_call",
                                tool_call={
                                    "id": fc.name,
                                    "name": fc.name,
                                    "arguments": dict(fc.args) if fc.args else {},
                                },
                            )
                if candidate and candidate.finish_reason:
                    yield StreamEvent(
                        type="done",
                        finish_reason=_normalize_finish(candidate.finish_reason, has_tool_calls),
                        usage=usage,
                    )
        except errors.APIError as exc:
            yield StreamEvent(type="error", error_message=str(exc))

    async def health_check(self) -> bool:
        from google.genai import types

        try:
            await self._client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1),
            )
            return True
        except Exception:
            return False
