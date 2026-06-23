import asyncio, textwrap
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.team import Team, TeamMember

async def main():
    async with AsyncSessionLocal() as db:
        teams = (await db.execute(select(Team).options(selectinload(Team.members).selectinload(TeamMember.agent)))).scalars().all()
        for t in teams:
            print("="*70); print("TAKIM:", t.name)
            for m in sorted(t.members, key=lambda x: x.position):
                a = m.agent
                print(f"\n  --- ROL: {m.role}  |  AGENT: {a.name} ---")
                print(f"    provider={a.provider} model={a.model} max_steps={a.max_steps} timeout={a.timeout_seconds}s")
                print(f"    tools={a.tool_names} fs={a.file_system_enabled}")
                print(f"    AGENT system_prompt:\n{textwrap.indent((a.system_prompt or '(boş)')[:600], '      ')}")
                print(f"    ROL prompt:\n{textwrap.indent((m.role_prompt or '(boş)')[:400], '      ')}")
asyncio.run(main())
