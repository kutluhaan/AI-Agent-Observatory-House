# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

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

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Project: AI Agent Observatory

Multi-tenant platform for running, testing, and observing AI agents.

### Stack

**Backend** — `backend/`
- FastAPI + Python 3.12, async everywhere (`async def`, `await`)
- SQLAlchemy 2.0 async ORM + asyncpg (PostgreSQL)
- Alembic for migrations (`backend/alembic/`)
- ClickHouse for traces/observability data
- Redis for caching and pub/sub
- Pydantic v2 for schemas
- `structlog` for logging (never use `print`)

**Frontend** — `frontend/`
- Next.js 14 App Router, TypeScript strict
- Tailwind CSS + `clsx`/`tailwind-merge` for class names
- `@xyflow/react` for workflow canvas
- Route groups: `(app)` for authenticated pages, `(auth)` for login/register
- No component library — custom UI components in `src/components/ui/`

**Infrastructure**
- Docker Compose: `docker-compose.dev.yml` for dev, `docker-compose.yml` for prod
- Three databases: PostgreSQL (relational), ClickHouse (traces), Redis (cache/ws)

### Backend Patterns

**File layout** — follow this strictly:
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

**DB sessions** — always use the `get_db` dependency from `app/api/deps.py`, never create sessions manually.

**Auth** — use `get_current_user` / `get_current_org` deps. Every endpoint that touches tenant data must scope queries to `organization_id`.

**Migrations** — after model changes: `alembic revision --autogenerate -m "description"`, then review the generated file before applying.

**LLM providers** — abstracted in `app/services/providers/`. Never call OpenAI/Anthropic/Gemini SDK directly in endpoint code; go through the provider service.

**Traces** — write to ClickHouse via `trace_collector.py`. Don't write trace data to PostgreSQL.

### Frontend Patterns

**API calls** — all in `src/lib/api/` (or nearest equivalent). Never fetch directly in components; call a typed API function.

**State** — React context in `src/contexts/`. Don't reach for external state management; context + useState covers existing needs.

**Class names** — always `cn()` (from `clsx`+`tailwind-merge`), never string concatenation.

**Components** — colocate page-specific components with the page. Only move to `src/components/` when used in 2+ places.

**Workflow canvas** — uses `@xyflow/react`. Custom node types live in `src/components/workflow/`. Don't import xyflow internals directly in pages.

### What NOT to do

- Don't add new top-level dependencies without asking — the stack is intentionally lean.
- Don't add synchronous SQLAlchemy calls; everything is async.
- Don't hardcode provider names as strings outside of `app/services/providers/`.
- Don't bypass multi-tenancy: every DB query touching user data must filter by `organization_id`.
- Don't write to ClickHouse from the API layer directly — use the trace service.
- Don't add `console.log` in frontend or `print` in backend — use `structlog` / browser devtools.

### Running locally

```bash
docker compose -f docker-compose.dev.yml up
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Tests

```bash
cd backend && pytest                          # unit tests
cd backend && pytest -m integration          # needs real PostgreSQL (use docker compose)
```

Integration tests hit a real DB — don't mock SQLAlchemy. Tests in `backend/tests/` follow `test_<module>.py` naming.
