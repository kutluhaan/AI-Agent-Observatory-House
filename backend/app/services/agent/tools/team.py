"""
Ekip (team) tool'ları — F8

- delegate(role, task): Coordinator bir alt-görevi role'e göre üyeye delege eder.
- team_share(title, content): paylaşılan panoya not yazar.
- team_board(): panodaki tüm notları okur.

Bağlam ToolContext'ten (team_id, team_run_id, current_role) okunur. Ekip dışında
çağrılırsa zarifçe hata mesajı döner. register_team_tools() lifespan'de çağrılır.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.team.roles import COORDINATOR


def register_team_tools() -> None:
    if "delegate" in ToolRegistry.all_names():
        return  # idempotent

    @ToolRegistry.register(
        "delegate",
        "Delegate a self-contained subtask to a teammate by their role (coordinator only). "
        "Returns the teammate's result.",
        {
            "type": "object",
            "properties": {
                "role": {"type": "string", "description": "Teammate role, e.g. researcher, worker, evaluator, planner."},
                "task": {"type": "string", "description": "Clear, self-contained instructions for the teammate."},
            },
            "required": ["role", "task"],
        },
    )
    async def delegate(ctx: ToolContext, role: str, task: str) -> str:
        from app.models.team import TeamMember
        from app.services.team.executor import build_member_runner, record_message

        if ctx.team_run_id is None or ctx.team_id is None:
            return "[delegate error: not running in a team context]"
        if ctx.current_role != COORDINATOR:
            return "[delegate error: only the coordinator can delegate]"

        # Bütçe: iletişim limiti (sektör pratiği — sonsuz delege/token israfını önler)
        from sqlalchemy import func
        from app.models.team import Team, TeamRunMessage
        team = (await ctx.db.execute(select(Team).where(Team.id == ctx.team_id))).scalar_one_or_none()
        cap = (getattr(team, "max_delegations", 12) or 12)
        used = (await ctx.db.execute(
            select(func.count()).select_from(TeamRunMessage).where(
                TeamRunMessage.team_run_id == ctx.team_run_id, TeamRunMessage.kind == "delegate",
            )
        )).scalar() or 0
        if used >= cap:
            return (
                f"[delegation budget reached ({cap}). Do NOT delegate further. Read the shared board "
                "with team_board() and synthesize the final answer NOW from the results gathered so far.]"
            )

        members = (await ctx.db.execute(
            select(TeamMember).where(TeamMember.team_id == ctx.team_id).options(selectinload(TeamMember.agent))
        )).scalars().all()
        target = next((m for m in members if m.role == role), None)
        if target is None:
            avail = ", ".join(sorted({m.role for m in members if m.role != COORDINATOR}))
            return f"[delegate error: no teammate with role '{role}'. Available roles: {avail}]"

        await record_message(ctx.db, ctx.team_run_id, "delegate", task, from_role=ctx.current_role, to_role=role, org_id=ctx.org_id)
        try:
            runner = await build_member_runner(
                ctx.db, ctx.redis, target, members,
                org_id=ctx.org_id, team_id=ctx.team_id, team_run_id=ctx.team_run_id,
                parent_trace_id=ctx.trace_id,
            )
            result = await runner.run(task)
            output = result.content
        except Exception as exc:  # noqa: BLE001
            output = f"[teammate '{role}' failed: {exc}]"
        await record_message(ctx.db, ctx.team_run_id, "result", output, from_role=role, to_role=ctx.current_role, org_id=ctx.org_id)
        return output

    @ToolRegistry.register(
        "team_share",
        "Post a note to the shared team board, visible to all teammates during this run.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the note."},
                "content": {"type": "string", "description": "The note content (findings, draft, etc.)."},
            },
            "required": ["title", "content"],
        },
    )
    async def team_share(ctx: ToolContext, title: str, content: str) -> str:
        from app.services.team.executor import record_message
        if ctx.team_run_id is None:
            return "[team_share error: not in a team context]"
        await record_message(ctx.db, ctx.team_run_id, "board", content, from_role=ctx.current_role, title=title, org_id=ctx.org_id)
        return f"Shared to team board: {title}"

    @ToolRegistry.register(
        "team_board",
        "Read all notes currently on the shared team board.",
        {"type": "object", "properties": {}},
    )
    async def team_board(ctx: ToolContext) -> str:
        from app.models.team import TeamRunMessage
        if ctx.team_run_id is None:
            return "[team_board error: not in a team context]"
        rows = (await ctx.db.execute(
            select(TeamRunMessage).where(
                TeamRunMessage.team_run_id == ctx.team_run_id,
                TeamRunMessage.kind == "board",
            ).order_by(TeamRunMessage.created_at)
        )).scalars().all()
        if not rows:
            return "The team board is empty."
        return "\n\n".join(f"[{r.from_role}] {r.title}: {r.content}" for r in rows)
