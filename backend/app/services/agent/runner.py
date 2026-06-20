"""
AgentRunner — ReAct execution loop implementasyonu.

Her çalıştırma:
  1. system_prompt + user_input ile başlar
  2. provider.complete() çağrılır (tool tanımları ile)
  3. finish_reason=stop → biter
  4. finish_reason=tool_calls → her tool çalıştırılır, sonuç mesaj geçmişine eklenir → 2'ye döner
  5. max_steps aşılırsa AgentMaxStepsError
  6. timeout aşılırsa AgentTimeoutError

Tüm adımlar Tracer aracılığıyla Redis Stream'e yazılır (M8 entegrasyonu).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.services.agent.base import (
    AgentConfig,
    AgentError,
    AgentMaxStepsError,
    AgentResult,
    AgentStreamEvent,
    AgentTimeoutError,
    AgentToolError,
    BaseAgent,
    HITLRejectedError,
    HITLTimeoutError,
)
from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.providers.base import (
    BaseLLMProvider,
    Message,
    ProviderError,
)
from app.services.trace_collector import Tracer

logger = structlog.get_logger()


def _merge_usage(total: dict[str, int], delta: dict[str, int]) -> None:
    for k, v in delta.items():
        total[k] = total.get(k, 0) + v


class AgentRunner(BaseAgent):
    """
    BaseAgent'ın tek somut implementasyonu.

    tool_context: call_agent gibi DB/Redis gerektiren tool'lar için inject edilir.
                  Basit tool'lar (echo, calculator) bunu kullanmaz.
    """

    def __init__(
        self,
        config: AgentConfig,
        provider: BaseLLMProvider,
        tracer: Tracer,
        tool_context: ToolContext | None = None,
        hitl: Any | None = None,         # HITLEngine — Any ile circular import önlenir
        ws_manager: Any | None = None,   # ConnectionManager
        history: list[Message] | None = None,  # Önceki thread mesajları (çok-turlu hafıza)
    ) -> None:
        super().__init__(config)
        self.provider = provider
        self.tracer = tracer
        self.tool_context = tool_context
        self.hitl = hitl
        self.ws_manager = ws_manager
        self.history = history or []

    # ─── Public API ───────────────────────────────────────

    async def run(self, user_input: str) -> AgentResult:
        """Timeout koruması ile tam çalıştırma."""
        # HITL beklemesi olabilecek agent'lara 10 dk ekstra süre tanı
        from app.services.hitl import HITL_TIMEOUT
        hitl_extra = HITL_TIMEOUT if self.config.hitl_tool_names else 0
        try:
            return await asyncio.wait_for(
                self._execute(user_input),
                timeout=self.config.timeout_seconds + hitl_extra,
            )
        except asyncio.TimeoutError:
            await self._emit_error("AGENT_TIMEOUT", f"Timed out after {self.config.timeout_seconds}s")
            await self.tracer.end(status="timeout")
            raise AgentTimeoutError(self.config.timeout_seconds)
        except ProviderError:
            raise  # already traced in _execute(); let agents.py handle code/status
        except (HITLRejectedError, HITLTimeoutError):
            await self.tracer.end(status="error")  # idempotent
            raise
        except AgentError:
            await self.tracer.end(status="error")  # idempotent — safe even if _execute ended it
            raise
        except Exception as exc:
            await self._emit_error("AGENT_UNEXPECTED_ERROR", str(exc))
            await self.tracer.end(status="error")
            raise

    async def stream(self, user_input: str) -> AsyncIterator[AgentStreamEvent]:
        """
        Token-by-token SSE generator. Timeout wrap'i dışarıdan (endpoint'ten) uygulanır.
        Tool call sırasında stream'i duraklatan ve devam ettiren döngü.
        """
        messages = self._build_messages(user_input)
        tool_defs = ToolRegistry.build_definitions(self.config.tool_names)
        step = 0
        total_usage: dict[str, int] = {}

        await self.tracer.start()

        try:
            while step < self.config.max_steps:
                step += 1
                await self.tracer.event("llm_call_start", {
                    "model": self.config.model,
                    "provider": self.config.provider,
                    "step": step,
                })

                # Streaming çağrısı
                accumulated_content = ""
                accumulated_tool_calls: list[dict[str, Any]] = []
                finish_reason = "stop"

                async for event in self.provider.stream(
                    messages,
                    self.config.model,
                    tools=tool_defs or None,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                ):
                    if event.type == "token" and event.content:
                        accumulated_content += event.content
                        yield AgentStreamEvent(type="token", content=event.content, step=step)

                    elif event.type == "tool_call" and event.tool_call:
                        accumulated_tool_calls.append(event.tool_call)

                    elif event.type == "done":
                        finish_reason = event.finish_reason or "stop"
                        if event.tool_call:
                            accumulated_tool_calls.append(event.tool_call)
                        if event.usage:
                            _merge_usage(total_usage, event.usage)

                    elif event.type == "error":
                        await self._emit_error("PROVIDER_STREAM_ERROR", event.error_message or "")
                        await self.tracer.end(status="error")
                        yield AgentStreamEvent(
                            type="error",
                            error_code="PROVIDER_STREAM_ERROR",
                            error_message=event.error_message,
                        )
                        return

                await self.tracer.event("llm_call_end", {
                    "model": self.config.model,
                    "finish_reason": finish_reason,
                    "step": step,
                })

                yield AgentStreamEvent(
                    type="step_done",
                    step=step,
                    finish_reason=finish_reason,
                )

                if finish_reason == "stop":
                    await self.tracer.end(
                        status="completed",
                        payload={"steps": step, "usage": total_usage},
                    )
                    yield AgentStreamEvent(
                        type="done",
                        trace_id=self.tracer.trace_id,
                        steps_taken=step,
                        finish_reason="stop",
                        total_usage=total_usage,
                    )
                    return

                if finish_reason == "tool_calls" and accumulated_tool_calls:
                    messages.append(Message(
                        role="assistant",
                        content=accumulated_content,
                        tool_calls=accumulated_tool_calls,
                    ))
                    for call in accumulated_tool_calls:
                        tool_name = call.get("name", "")
                        raw_arguments = call.get("arguments", {})
                        call_id = call.get("id", "")

                        # Normalize arguments to dict for AgentStreamEvent (providers may return JSON string)
                        if isinstance(raw_arguments, str):
                            try:
                                arguments_dict: dict[str, Any] = json.loads(raw_arguments) if raw_arguments else {}
                            except json.JSONDecodeError:
                                arguments_dict = {}
                        else:
                            arguments_dict = raw_arguments or {}

                        yield AgentStreamEvent(
                            type="tool_call_start",
                            tool_name=tool_name,
                            tool_arguments=arguments_dict,
                            step=step,
                        )
                        await self.tracer.event("tool_call_start", {
                            "name": tool_name,
                            "arguments": arguments_dict,
                            "step": step,
                        })

                        # HITL gate — insan onayı gerekiyorsa askıya al
                        if self.hitl and tool_name in self.config.hitl_tool_names:
                            request_id = await self.hitl.create_request(
                                trace_id=self.tracer.trace_id,
                                org_id=str(self.config.org_id),
                                tool_name=tool_name,
                                tool_arguments=arguments_dict,
                            )
                            await self.tracer.event("hitl_requested", {
                                "request_id": request_id,
                                "tool_name": tool_name,
                                "arguments": arguments_dict,
                                "step": step,
                            })
                            if self.ws_manager:
                                await self.ws_manager.broadcast(str(self.config.org_id), {
                                    "type": "hitl_requested",
                                    "request_id": request_id,
                                    "trace_id": self.tracer.trace_id,
                                    "tool_name": tool_name,
                                    "tool_arguments": arguments_dict,
                                })
                            yield AgentStreamEvent(
                                type="hitl_requested",
                                tool_name=tool_name,
                                tool_arguments=arguments_dict,
                                step=step,
                                hitl_request_id=request_id,
                            )
                            resolution = await self.hitl.wait_for_resolution(request_id)
                            await self.tracer.event("hitl_resolved", {
                                "request_id": request_id,
                                "action": resolution.action,
                                "modified_arguments": resolution.modified_arguments,
                                "step": step,
                            })
                            yield AgentStreamEvent(
                                type="hitl_resolved",
                                tool_name=tool_name,
                                step=step,
                                hitl_request_id=request_id,
                                hitl_action=resolution.action,
                                hitl_modified_arguments=resolution.modified_arguments,
                            )
                            if resolution.action == "rejected":
                                raise HITLRejectedError(tool_name, resolution.reason or "")
                            if resolution.action == "modified" and resolution.modified_arguments:
                                arguments_dict = resolution.modified_arguments

                        tool_result = await self._execute_tool(tool_name, arguments_dict)

                        await self.tracer.event("tool_call_end", {
                            "name": tool_name,
                            "result": tool_result,
                            "step": step,
                        })
                        yield AgentStreamEvent(
                            type="tool_call_end",
                            tool_name=tool_name,
                            tool_result=tool_result,
                            step=step,
                        )

                        messages.append(Message(
                            role="tool",
                            content=tool_result,
                            tool_call_id=call_id,
                        ))
                    continue

                # Bilinmeyen finish_reason — güvenli çıkış
                await self.tracer.end(status="completed", payload={"steps": step})
                yield AgentStreamEvent(
                    type="done",
                    trace_id=self.tracer.trace_id,
                    steps_taken=step,
                    finish_reason=finish_reason,
                    total_usage=total_usage,
                )
                return

            # Max steps
            await self.tracer.end(status="max_steps_exceeded")
            err = AgentMaxStepsError(self.config.max_steps)
            yield AgentStreamEvent(
                type="error",
                error_code=err.code,
                error_message=err.message,
            )

        except ProviderError as exc:
            await self._emit_error(exc.code, exc.message)
            await self.tracer.end(status="error")
            yield AgentStreamEvent(type="error", error_code=exc.code, error_message=exc.message)
        except (HITLRejectedError, HITLTimeoutError) as exc:
            await self.tracer.end(status="error")  # idempotent
            yield AgentStreamEvent(type="error", error_code=exc.code, error_message=exc.message)
        except AgentError as exc:
            await self.tracer.end(status="error")  # idempotent — safe if already ended
            yield AgentStreamEvent(type="error", error_code=exc.code, error_message=exc.message)
        except Exception as exc:
            logger.error("agent.stream.unexpected_error", error=str(exc))
            await self._emit_error("AGENT_UNEXPECTED_ERROR", str(exc))
            await self.tracer.end(status="error")
            yield AgentStreamEvent(
                type="error",
                error_code="AGENT_UNEXPECTED_ERROR",
                error_message=str(exc),
            )
        finally:
            # Guarantee agent_end is always written — covers GeneratorExit thrown when
            # the SSE generator is closed early (e.g. client timeout or disconnect).
            # tracer.end() is idempotent: no-op if already called in a normal path.
            await self.tracer.end(status="interrupted")

    # ─── Internal ─────────────────────────────────────────

    async def _execute(self, user_input: str) -> AgentResult:
        """Blocking execution loop (run() tarafından kullanılır)."""
        messages = self._build_messages(user_input)
        tool_defs = ToolRegistry.build_definitions(self.config.tool_names)
        step = 0
        total_usage: dict[str, int] = {}

        await self.tracer.start()

        while step < self.config.max_steps:
            step += 1
            await self.tracer.event("llm_call_start", {
                "model": self.config.model,
                "provider": self.config.provider,
                "step": step,
            })

            try:
                result = await self.provider.complete(
                    messages,
                    self.config.model,
                    tools=tool_defs or None,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            except ProviderError as exc:
                await self._emit_error(exc.code, exc.message)
                await self.tracer.end(status="error")
                raise  # re-raise ProviderError directly — preserves code and status_code

            _merge_usage(total_usage, result.usage)
            await self.tracer.event("llm_call_end", {
                "model": self.config.model,
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "step": step,
            })

            if result.finish_reason == "stop":
                await self.tracer.end(
                    status="completed",
                    payload={"steps": step, "usage": total_usage},
                )
                return AgentResult(
                    content=result.content,
                    steps_taken=step,
                    trace_id=self.tracer.trace_id,
                    finish_reason="stop",
                    total_usage=total_usage,
                )

            if result.finish_reason == "tool_calls" and result.tool_calls:
                messages.append(Message(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                ))
                for call in result.tool_calls:
                    tool_name = call.get("name", "")
                    raw_arguments = call.get("arguments", {})
                    call_id = call.get("id", "")

                    # Normalize arguments to dict — OpenAI non-streaming returns JSON strings
                    if isinstance(raw_arguments, str):
                        try:
                            arguments: dict[str, Any] = json.loads(raw_arguments) if raw_arguments else {}
                        except json.JSONDecodeError:
                            arguments = {}
                    else:
                        arguments = raw_arguments or {}

                    await self.tracer.event("tool_call_start", {
                        "name": tool_name,
                        "arguments": arguments,
                        "step": step,
                    })

                    # HITL gate — insan onayı gerekiyorsa askıya al
                    if self.hitl and tool_name in self.config.hitl_tool_names:
                        arguments = await self._hitl_gate(tool_name, arguments, step)

                    tool_result = await self._execute_tool(tool_name, arguments)
                    await self.tracer.event("tool_call_end", {
                        "name": tool_name,
                        "result": tool_result,
                        "step": step,
                    })
                    messages.append(Message(
                        role="tool",
                        content=tool_result,
                        tool_call_id=call_id,
                    ))
                continue

            # Bilinmeyen finish_reason — güvenli çıkış
            await self.tracer.end(status="completed", payload={"steps": step})
            return AgentResult(
                content=result.content,
                steps_taken=step,
                trace_id=self.tracer.trace_id,
                finish_reason=result.finish_reason,
                total_usage=total_usage,
            )

        # Max steps aşıldı
        await self.tracer.end(status="max_steps_exceeded")
        raise AgentMaxStepsError(self.config.max_steps)

    async def _hitl_gate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        step: int,
    ) -> dict[str, Any]:
        """
        Sync path (run/_execute) için HITL gate.
        SSE event yoktur — sadece tracer + WebSocket bildirimi.
        HITLRejectedError veya HITLTimeoutError fırlatabilir.
        """
        request_id = await self.hitl.create_request(
            trace_id=self.tracer.trace_id,
            org_id=str(self.config.org_id),
            tool_name=tool_name,
            tool_arguments=arguments,
        )
        await self.tracer.event("hitl_requested", {
            "request_id": request_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "step": step,
        })
        if self.ws_manager:
            await self.ws_manager.broadcast(str(self.config.org_id), {
                "type": "hitl_requested",
                "request_id": request_id,
                "trace_id": self.tracer.trace_id,
                "tool_name": tool_name,
                "tool_arguments": arguments,
            })

        resolution = await self.hitl.wait_for_resolution(request_id)

        await self.tracer.event("hitl_resolved", {
            "request_id": request_id,
            "action": resolution.action,
            "modified_arguments": resolution.modified_arguments,
            "step": step,
        })

        if resolution.action == "rejected":
            raise HITLRejectedError(tool_name, resolution.reason or "")

        if resolution.action == "modified" and resolution.modified_arguments:
            return resolution.modified_arguments

        return arguments

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any] | str) -> str:
        """Tool handler'ı çalıştırır, hataları AgentToolError'a çevirir.

        arguments: OpenAI JSON string döndürür, Anthropic dict döndürür — her ikisini normalize eder.
        """
        try:
            handler = ToolRegistry.get(tool_name)
        except KeyError:
            await self._emit_error("AGENT_TOOL_ERROR", f"Unknown tool: '{tool_name}'")
            raise AgentToolError(f"Unknown tool: '{tool_name}'")

        # OpenAI complete() tool çağrılarında arguments JSON string olarak gelir
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                logger.warning("agent.tool_error.invalid_json", tool=tool_name, raw=arguments)
                return f"[Tool error: invalid JSON arguments — {exc}]"

        ctx = self.tool_context or ToolContext(
            org_id=self.config.org_id,
            trace_id=self.tracer.trace_id,
            db=None,
            redis=self.tracer.redis,
        )
        try:
            result = await handler.handler(ctx, **arguments)
            return str(result)
        except AgentError:
            raise
        except Exception as exc:
            logger.warning("agent.tool_error", tool=tool_name, error=str(exc))
            return f"[Tool error: {exc}]"

    async def _emit_error(self, code: str, message: str) -> None:
        await self.tracer.event("error", {"code": code, "message": message})

    def _build_messages(self, user_input: str) -> list[Message]:
        messages: list[Message] = []
        if self.config.system_prompt:
            messages.append(Message(role="system", content=self.config.system_prompt))
        # Çok-turlu hafıza: önceki thread mesajları (user/assistant final metinleri)
        messages.extend(self.history)
        messages.append(Message(role="user", content=user_input))
        return messages
