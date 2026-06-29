# CLAUDE.md — AI Agent Observatory

**Project:** Multi-tenant AI agent platform with observability, testing, and human-in-the-loop approval.  
**Stack:** FastAPI (Python 3.12), Next.js 14 (TypeScript), PostgreSQL 16, Redis 7, ClickHouse 24.

This document captures tech patterns, naming conventions, and decision criteria specific to this codebase.

---

## Architecture Overview

### High-Level Flow

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

### Key Principles

- **Multi-tenant by default:** Every resource tied to `organization_id`. No cross-org data leakage.
- **Auth via JWT in httpOnly cookie:** Frontend sends `credentials: "include"` on all fetches.
- **Org context in JWT:** `org_id`, `org_slug`, `role` decoded from token; no DB query per request.
- **Async throughout:** FastAPI, asyncpg, async Redis, async ClickHouse.
- **Error responses standardized:** `{ success: false, error: { code, message } }` with HTTP status.
- **Tool registry at startup:** Built-in tools, MCP tools, custom tools registered once on app start.
- **Event streaming:** Agent runs emit events to Redis Stream → ClickHouse consumer → live WebSocket push.

---

## Backend Patterns

### Naming & Conventions

**Files:**
- `*_service.py` → service/logic module
- `*_provider.py` → LLM provider implementation
- `test_*.py` → pytest test module

**Classes & Functions:**
- `BaseXXX` → Abstract base / interface
- `get_xxx()` → Dependency injection or getter
- `async def` → all I/O operations

**Database Models:**
- PK: UUID with `server_default=text("gen_random_uuid()")`
- Foreign keys: explicit with `ondelete="CASCADE"` or `"SET NULL"`
- Timestamps: `created_at`, `updated_at` both `DateTime(timezone=True)`
- Tenant scoping: every model has `organization_id` FK (enforce in service layer)
- Complex data: JSONB columns for lists/dicts
- Encrypted fields: stored as Text, decrypted on read via `encryption.py`

**Error Codes:**
- SCREAMING_SNAKE_CASE: `PROVIDER_NOT_CONFIGURED`, `INVALID_TOKEN`, `ORG_DEACTIVATED`, etc.
- Format: `AppError(code, message, status)`

### Dependency Injection

FastAPI `Depends()` is the central DI mechanism. Key dependencies:
- `get_current_user` → CurrentUser (auth required)
- `get_tenant_context` → TenantContext (org context from JWT)
- `get_db` → AsyncSession
- `require_role(["owner", "admin"])` → role gatekeeper

### Service Layer Pattern

Business logic lives in `services/`, not endpoints. Always filter by `org_id`:

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

All errors inherit from `AppError`:

```python
raise AppError("AGENT_NOT_FOUND", "Agent not found.", 404)
raise UnauthorizedError("INVALID_TOKEN", "Authentication required.")
raise ForbiddenError("ORG_DEACTIVATED", "Organization deactivated.")
```

### Async & Transactions

`get_db` auto-commits on success, rollbacks on exception:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Testing

**Unit tests** (no DB required):
```python
def test_encode_decode_token():
    token = jwt_service.encode_access_token({"sub": "user-id"})
    payload = jwt_service.decode_access_token(token)
    assert payload["sub"] == "user-id"
```

**Integration tests** (requires PostgreSQL + Redis):
```python
@pytest.mark.integration
async def test_register_login_flow(client: AsyncClient, db: AsyncSession):
    resp = await client.post("/auth/register", json={"email": "...", "password": "..."})
    assert resp.status_code == 201
    assert "access_token" in resp.cookies
```

---

## Frontend Patterns

### Naming & Conventions

**Files:**
- `page.tsx` → Route page (Next.js App Router)
- `layout.tsx` → Route layout
- Component files: kebab-case

**React:**
- Functional components only
- `"use client"` directive at top of client components
- `forwardRef` for components that expose DOM elements

**Styling:**
- Tailwind CSS utility-first
- `clsx` or `cn` for conditional classes
- Dark theme by default (bg-zinc-900, text-zinc-100)

**API Client:**
- Centralized: `@/lib/api.ts` (single export: `api`)
- Methods: `api.get<T>()`, `api.post<T>()`, `api.patch<T>()`, `api.delete()`
- Auto-throws `ApiError` on non-2xx
- Auto-refresh on 401

### Key Patterns

**Authentication Flow:**

1. Initial load: `AuthProvider` calls `GET /auth/me`
2. Login/Signup: POST to `/auth/register` or `/auth/login`, backend sets `Set-Cookie`
3. Auto-Refresh: On 401, POST `/auth/refresh`, retry original request
4. Logout: Call `logout()` from `useAuth()`, backend revokes token

**SSE Streaming (Agent Chat):**

```typescript
export async function* streamAgentRun(agentId: string, input: string) {
  const response = await fetch(`${BASE_URL}/agents/${agentId}/run`, {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({ input, stream: true }),
  });
  
  const reader = response.body?.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const text = new TextDecoder().decode(value);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
```

**WebSocket Live Traces:**

```typescript
export function connectTraces(orgId: string, callback: (event: any) => void) {
  const ws = new WebSocket(`wss://api/ws/traces`);
  ws.onmessage = (e) => callback(JSON.parse(e.data));
  return () => ws.close();
}
```

### Component Guidelines

**UI Components (headless):**
- No business logic, only presentation
- Props interfaces extend HTMLAttributes
- Tailwind + clsx for styling

**Page Components:**
- Handle layout, routing, page logic
- Can be async (Server Components)
- If interactive, use `"use client"`

**Custom Hooks:**
- Encapsulate logic + state
- Start with `use` prefix
- Client components only

---

## Database & Tenancy

### Key Principle: Org-Scoped Everything

Every resource tied to `organization_id`. **Always filter in service layer:**

```python
# CORRECT:
async def get_agent(db, org_id, agent_id):
    return await db.execute(
        select(Agent).where(
            Agent.organization_id == org_id,  # ← ALWAYS
            Agent.id == agent_id,
        )
    )

# WRONG:
async def get_agent(db, agent_id):
    return await db.get(Agent, agent_id)  # Security bug!
```

### Schema Highlights

**Users & Organizations:**
```
users (id, email, full_name, password_hash, is_verified, ...)
organizations (id, name, slug, plan, is_active, created_by)
organization_members (id, organization_id, user_id, role, joined_at)
```

**Agents & Config:**
```
agents (id, organization_id, name, system_prompt, provider, model, tool_names[], ...)
agent_prompt_versions (id, agent_id, version, system_prompt, created_at)
```

**Traces (ClickHouse, not PostgreSQL):**
```
traces (org_id, run_id, step_id, type, data, created_at)
  └─ 30-day TTL
```

**Providers & Credentials:**
```
provider_credentials (id, organization_id, provider_name, encrypted_key, created_at)
  ├─ Key hierarchy: org key > platform .env
  └─ Key never returned in API responses
```

### Migrations (Alembic)

```bash
docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "..."
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
docker compose -f docker-compose.dev.yml exec backend alembic downgrade -1
```

---

## Authentication & Authorization

### JWT & Cookies (M3)

**Encoding (RS256):**
```python
def encode_access_token(payload: dict) -> str:
    token = jwt.encode(
        {
            **payload,
            "jti": str(uuid.uuid4()),
            "exp": datetime.utcnow() + timedelta(minutes=15),
        },
        settings.jwt_private_key,
        algorithm="RS256",
    )
    return token
```

**Storage (httpOnly cookie):**
```python
response.set_cookie(
    key="access_token",
    value=access_token,
    max_age=15 * 60,
    httponly=True,
    secure=True,
    samesite="Lax",
)
```

**Frontend (auto-attach):**
```typescript
const response = await fetch(`${BASE_URL}${endpoint}`, {
    credentials: "include",
});
```

### Refresh Token Flow (M4)

Access token: 15 min, refresh token: 7 days.

### Role-Based Access Control (M5-M6)

**Role hierarchy:** member < admin < owner

```python
def require_role(allowed_roles: list[str]):
    async def check_role(tenant: TenantContext = Depends(get_tenant_context)):
        if tenant.role not in allowed_roles:
            raise ForbiddenError("INSUFFICIENT_ROLE", "...")
        return tenant
    return Depends(check_role)
```

### Org Switching (M4)

User can have multiple orgs. JWT stores active org context.

---

## Summary of Key Rules

1. **Org scope first:** Every query filters by `organization_id`.
2. **Async everywhere:** FastAPI, SQLAlchemy, Redis, ClickHouse.
3. **Error codes SCREAMING_SNAKE_CASE:** `AGENT_NOT_FOUND`, not `agent_not_found`.
4. **JWT in httpOnly cookies:** Frontend sends `credentials: "include"` on all fetches.
5. **Services before endpoints:** Business logic in `services/`.
6. **Tests split:** unit/ for no-DB, integration/ for DB.
7. **Client API centralized:** Single error handler, auto-refresh on 401.
8. **Components are headless:** UI components have no business logic.
9. **Tailwind + clsx:** Dark theme by default.
10. **Tool registry at startup:** Built-in, MCP, custom tools registered once, accessible to all agents.
