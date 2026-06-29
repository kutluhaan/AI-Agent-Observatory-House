# CLAUDE.md — AI Agent Observatory

Behavioral guidelines + project-specific patterns for this codebase.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Project: AI Agent Observatory

**Project:** Multi-tenant AI agent platform with observability, testing, and human-in-the-loop approval.  
**Stack:** FastAPI (Python 3.12), Next.js 14 (TypeScript), PostgreSQL 16, Redis 7, ClickHouse 24.

### Architecture

```
Browser (Next.js 14)
    ├→ /auth/* (login, signup, verify-email, org-switch)
    ├→ /(app)/* (protected routes via AuthProvider)
    └→ API calls via @/lib/api.ts (httpOnly cookie auth)
         ↓
FastAPI Backend (port 8000)
    ├→ [AuthMiddleware] JWT from cookie → request.state.current_user
    ├→ [Routers] /auth, /organizations, /agents, /providers, /traces, etc.
    ├→ [Services] business logic (decoupled from FastAPI)
    ├→ [Models] SQLAlchemy ORM (org-scoped)
    └→ [Storage]
        ├→ PostgreSQL 16: users, orgs, agents, test suites, credentials
        ├→ Redis 7: auth tokens, live trace events, session cache
        └→ ClickHouse 24: trace history (30-day TTL, org-scoped)
```

**Key principles:**
- **Multi-tenant by default:** Every resource tied to `organization_id`. No cross-org data leakage.
- **Auth via JWT in httpOnly cookie:** Frontend sends `credentials: "include"` on all fetches.
- **Org context in JWT:** `org_id`, `org_slug`, `role` decoded from token; no DB query per request.
- **Async throughout:** FastAPI, asyncpg, async Redis, async ClickHouse.
- **Event streaming:** Agent runs emit events to Redis Stream → ClickHouse consumer → live WebSocket push.

---

## Backend Patterns

### File Layout

```
app/api/v1/<resource>.py   → FastAPI router, request parsing, calls service
app/services/<resource>/   → business logic, no HTTP concerns
app/models/<resource>.py   → SQLAlchemy model
app/schemas/<resource>.py  → Pydantic request/response schemas
```

**Adding a new endpoint:**
1. Schema in `app/schemas/`
2. Model in `app/models/` if new table → Alembic migration
3. Service logic in `app/services/`
4. Router in `app/api/v1/` → register in `app/main.py`

### Naming Conventions

- Files: `*_service.py` (logic), `*_provider.py` (LLM provider), `test_*.py` (tests)
- Classes: `BaseXXX` for abstract bases, `get_xxx()` for DI/getters
- DB PKs: UUID with `server_default=text("gen_random_uuid()")`
- Timestamps: `created_at`, `updated_at` both `DateTime(timezone=True)`
- Error codes: SCREAMING_SNAKE_CASE (`AGENT_NOT_FOUND`, `INVALID_TOKEN`)

### Dependency Injection

```python
get_current_user    # → CurrentUser (auth required)
get_tenant_context  # → TenantContext (org context from JWT)
get_db              # → AsyncSession
require_role(["owner", "admin"])  # role gatekeeper
```

### Service Layer — Always Scope to org_id

```python
async def get_agent(db: AsyncSession, org_id: UUID, agent_id: UUID) -> Agent | None:
    result = await db.execute(
        select(Agent).where(
            Agent.organization_id == org_id,  # ← ALWAYS
            Agent.id == agent_id,
        )
    )
    return result.scalar_one_or_none()
```

### Error Handling

```python
raise AppError("AGENT_NOT_FOUND", "Agent not found.", 404)
raise UnauthorizedError("INVALID_TOKEN", "Authentication required.")
raise ForbiddenError("ORG_DEACTIVATED", "Organization deactivated.")
```

### LLM Providers

Abstracted in `app/services/providers/`. Never call OpenAI/Anthropic/Gemini SDK directly in endpoint code.

### Traces

Write to ClickHouse via `trace_collector.py`. Don't write trace data to PostgreSQL.

### Migrations

```bash
docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "..."
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

Always review the generated file before applying.

### Testing

**Unit tests** (no DB): `tests/unit/test_*.py`

**Integration tests** (requires PostgreSQL + Redis):
```python
@pytest.mark.integration
async def test_register_login_flow(client: AsyncClient, db: AsyncSession):
    ...
```

```bash
cd backend && pytest                  # unit only
cd backend && pytest -m integration   # needs docker compose running
```

Don't mock SQLAlchemy in integration tests — hit a real DB.

---

## Frontend Patterns

### File Layout

- `src/app/(app)/` — authenticated pages
- `src/app/(auth)/` — login, register, verify-email
- `src/components/ui/` — headless UI primitives (no business logic)
- `src/components/workflow/` — `@xyflow/react` custom node types
- `src/contexts/` — React context (AuthContext)
- `src/lib/api.ts` — centralized API client

### API Calls

Never fetch directly in components. Use `src/lib/api.ts`:

```typescript
api.get<T>()   api.post<T>()   api.patch<T>()   api.delete()
```

Auto-throws `ApiError` on non-2xx, auto-refresh on 401.

### Styling

- Always `cn()` (clsx + tailwind-merge), never string concatenation.
- Dark theme by default (`bg-zinc-900`, `text-zinc-100`).

### Components

- Colocate page-specific components with the page.
- Move to `src/components/` only when used in 2+ places.
- Functional components only. `"use client"` at top for interactive components.
- Workflow canvas: don't import xyflow internals directly in pages.

### State

React context in `src/contexts/`. Don't reach for external state management.

---

## What NOT to Do

- Don't add new top-level dependencies without asking.
- Don't add synchronous SQLAlchemy calls; everything is async.
- Don't hardcode provider names as strings outside `app/services/providers/`.
- Don't bypass multi-tenancy: every DB query touching user data must filter by `organization_id`.
- Don't write to ClickHouse from the API layer — use `trace_collector.py`.
- Don't add `console.log` in frontend or `print` in backend — use `structlog` / browser devtools.
- Don't return encrypted API keys in API responses.

---

## Running Locally

```bash
docker compose -f docker-compose.dev.yml up
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```
