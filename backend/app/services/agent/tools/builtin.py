"""
Built-in tool'lar — tüm org'lara hazır araçlar.

echo       : Temel test tool'u. Girdiyi olduğu gibi döner.
calculator : Güvenli aritmetik. eval() kullanmaz; ast.literal_eval tabanlı parser.
call_agent : Multi-agent orchestration. Başka bir agent'ı çağırır.

register_builtin_tools() uygulama başlangıcında (lifespan) çağrılır.
"""
from __future__ import annotations

import ast
import operator
import uuid

import structlog

from app.services.agent.registry import ToolContext, ToolRegistry

logger = structlog.get_logger()


def register_builtin_tools() -> None:
    """Idempotent — birden fazla çağrılabilir."""
    try:
        ToolRegistry.get("echo")
        return  # already registered
    except KeyError:
        pass

    # ── echo ──────────────────────────────────────────────

    @ToolRegistry.register(
        name="echo",
        description="Returns the given text unchanged. Useful for testing tool call flow.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo back."},
            },
            "required": ["text"],
        },
    )
    async def echo(ctx: ToolContext, text: str) -> str:
        return text

    # ── calculator ────────────────────────────────────────

    @ToolRegistry.register(
        name="calculator",
        description=(
            "Evaluates a simple arithmetic expression and returns the numeric result. "
            "Supports +, -, *, /, ** and parentheses. No variables or functions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression, e.g. '(3 + 4) * 2'.",
                },
            },
            "required": ["expression"],
        },
    )
    async def calculator(ctx: ToolContext, expression: str) -> str:
        try:
            result = _safe_eval(expression)
            return str(result)
        except Exception as exc:
            return f"[Calculator error: {exc}]"

    # ── call_agent ────────────────────────────────────────

    @ToolRegistry.register(
        name="call_agent",
        description=(
            "Calls another agent by its ID and returns its response. "
            "Use this to delegate a sub-task to a specialized agent."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "UUID of the target agent.",
                },
                "input": {
                    "type": "string",
                    "description": "The message/task to send to the target agent.",
                },
            },
            "required": ["agent_id", "input"],
        },
    )
    async def call_agent(ctx: ToolContext, agent_id: str, input: str) -> str:
        if ctx.db is None:
            return "[call_agent error: no database context available]"
        try:
            return await _run_sub_agent(ctx, agent_id, input)
        except Exception as exc:
            logger.warning("call_agent.error", agent_id=agent_id, error=str(exc))
            return f"[call_agent error: {exc}]"

    # ── think ─────────────────────────────────────────────

    @ToolRegistry.register(
        name="think",
        description=(
            "Think step by step before acting. Use this to reason about the problem, "
            "plan your approach, or reflect on tool results. The thought is shown to the "
            "user as a reasoning step but does not perform any action."
        ),
        parameters={
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Your reasoning or plan."},
            },
            "required": ["thought"],
        },
    )
    async def think(ctx: ToolContext, thought: str) -> str:
        # İçerik tool argümanlarında zaten taşınıyor (UI reasoning bloğu olarak render eder).
        return "Acknowledged."

    # ── write_todos ───────────────────────────────────────

    @ToolRegistry.register(
        name="write_todos",
        description=(
            "Write or update a task checklist for a multi-step job. Call this with the FULL "
            "list each time, updating each item's status as you progress "
            "(pending → in_progress → completed). The list is shown to the user and updates live."
        ),
        parameters={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The full to-do list (re-send all items every time).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "What to do."},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    )
    async def write_todos(ctx: ToolContext, todos: list) -> str:
        if not isinstance(todos, list):
            return "[write_todos error: 'todos' must be a list]"
        done = sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "completed")
        return f"To-do list updated: {len(todos)} item(s), {done} completed."

    # ── ask_user ──────────────────────────────────────────

    @ToolRegistry.register(
        name="ask_user",
        description=(
            "Ask the user a question and wait for their answer before continuing. Use when you "
            "need a decision, preference, or missing information. Provide 'options' for a choice "
            "(set 'multi' true to allow multiple selections); the user can also type a free-text "
            "answer. Returns the user's answer."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask."},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional choices to present.",
                },
                "multi": {
                    "type": "boolean",
                    "description": "Allow selecting multiple options. Default false.",
                },
            },
            "required": ["question"],
        },
    )
    async def ask_user(ctx: ToolContext, question: str, options: list | None = None, multi: bool = False) -> str:
        # Runner bu tool'u (hitl engine varsa) yakalayıp kullanıcıdan yanıt alır.
        # Buraya düşülürse mekanizma yok demektir.
        return "(User input is not available in this context.)"


# ─── Safe arithmetic evaluator ───────────────────────────

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)


def _eval_node(node: ast.expr) -> float:  # type: ignore[return]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_fn = _ALLOWED_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_fn = _ALLOWED_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_eval_node(node.operand))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


# ─── Sub-agent runner (call_agent implementation) ─────────

async def _run_sub_agent(ctx: ToolContext, agent_id: str, user_input: str) -> str:
    """
    Hedef agent'ı yükler, ayrı bir Tracer ile çalıştırır.
    parent_trace_id üst trace'e bağlar.
    """
    from sqlalchemy import select

    from app.models.agent import Agent
    from app.services.agent.base import AgentConfig
    from app.services.agent.runner import AgentRunner
    from app.services.providers.factory import get_provider
    from app.services.trace_collector import Tracer

    try:
        target_id = uuid.UUID(agent_id)
    except ValueError:
        return f"[call_agent error: '{agent_id}' is not a valid UUID]"

    result = await ctx.db.execute(
        select(Agent).where(
            Agent.id == target_id,
            Agent.organization_id == ctx.org_id,
            Agent.is_active == True,  # noqa: E712
        )
    )
    agent_row = result.scalar_one_or_none()
    if agent_row is None:
        return f"[call_agent error: agent '{agent_id}' not found or inactive]"

    config = AgentConfig(
        agent_id=agent_row.id,
        org_id=ctx.org_id,
        name=agent_row.name,
        system_prompt=agent_row.system_prompt,
        provider=agent_row.provider,
        model=agent_row.model,
        temperature=agent_row.temperature,
        max_tokens=agent_row.max_tokens,
        max_steps=agent_row.max_steps,
        timeout_seconds=agent_row.timeout_seconds,
        tool_names=agent_row.tool_names or [],
        hitl_tool_names=agent_row.hitl_tool_names or [],
    )

    provider = await get_provider(ctx.db, ctx.org_id, config.provider)

    sub_tracer = Tracer(
        redis=ctx.redis,
        organization_id=str(ctx.org_id),
        name=f"sub-agent:{agent_row.name}",
        parent_trace_id=ctx.trace_id,
    )

    sub_ctx = ToolContext(
        org_id=ctx.org_id,
        trace_id=sub_tracer.trace_id,
        db=ctx.db,
        redis=ctx.redis,
    )

    try:
        from app.services.hitl import get_hitl_engine
        hitl = get_hitl_engine()
    except RuntimeError:
        hitl = None

    runner = AgentRunner(
        config=config,
        provider=provider,
        tracer=sub_tracer,
        tool_context=sub_ctx,
        hitl=hitl,
    )

    agent_result = await runner.run(user_input)
    return agent_result.content
