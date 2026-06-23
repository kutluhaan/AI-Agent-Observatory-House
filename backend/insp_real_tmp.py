import asyncio, textwrap
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.team import Team, TeamMember

async def main():
    async with AsyncSessionLocal() as db:
        teams = (await db.execute(select(Team).options(selectinload(Team.members).selectinload(TeamMember.agent)))).scalars().all()
        real = [t for t in teams if any((m.agent.system_prompt or "x") != "x" or len(m.role_prompt or "") > 6 for m in t.members)]
        print(f"Toplam takım: {len(teams)} | gerçek (dolu promptlu): {len(real)}")
        for t in real:
            print("="*70); print("TAKIM:", t.name, "| org:", str(t.organization_id)[:8])
            for m in sorted(t.members, key=lambda x: x.position):
                a = m.agent
                print(f"\n  ROL={m.role} AGENT='{a.name}' provider={a.provider} model={a.model} max_steps={a.max_steps} timeout={a.timeout_seconds}s tools={a.tool_names}")
                print(f"  AGENT system_prompt:\n{textwrap.indent((a.system_prompt or '(boş)'), '    ')}")
                print(f"  ROL prompt:\n{textwrap.indent((m.role_prompt or '(boş)'), '    ')}")
asyncio.run(main())
