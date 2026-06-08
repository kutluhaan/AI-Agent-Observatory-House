# AI Agent Observatory

**Test, observe, and orchestrate AI agents — with your team, in one place.**

AI Agent Observatory is a multi-tenant platform for teams that build and rely on AI agents. It brings together **running agents**, **seeing what they did**, **pausing for human approval when it matters**, and **measuring quality** — instead of scattering logs, scripts, and one-off dashboards across tools.

---

## Why this project exists

Teams shipping agent features often hit the same walls:

- Hard to know *what the agent actually did* step by step  
- No consistent way to *test* behavior before production  
- Risky actions need a *human in the loop*, but wiring that is ad hoc  
- Multiple customers or internal teams need *isolated data* and *clear roles*

Observatory is built to address those needs in a single product-shaped codebase: observable runs, structured testing, optional human approval, and organization-scoped access from day one in the design.

---

## Who it’s for

- **Engineering teams** building LLM-powered products and internal agents  
- **Platform / ML engineers** who care about traces, regressions, and evals  
- **Organizations** that need separate workspaces (tenants) with members, roles, and invitations  

You don’t need to be an infra expert to understand the goal: **make agents understandable, testable, and governable.**

---

## What the platform will let you do

| Capability | In plain terms |
|------------|----------------|
| **Multi-tenant workspaces** | Each organization has its own members, roles, and data boundary. |
| **Authentication & access** | Sign up, sign in, switch organization, invite colleagues — with role-based permissions. |
| **Agent execution** | Run agents against multiple model providers (cloud APIs and local models). |
| **Observability** | Follow each run: prompts, tool calls, timings, and outcomes in a trace-oriented UI. |
| **Human-in-the-loop (HITL)** | Pause the agent at critical steps until a person approves, rejects, or edits. |
| **Testing & evaluation** | Define test suites (including RAG-style checks), run them, and compare results over time. |
| **Reference agent** | A “personal research” style agent demonstrates the full stack end to end. |

Capabilities are delivered in **milestones** (see [Roadmap](#roadmap)); the repo is actively evolving.

---

## How it fits together (conceptual)

```text
  Your team (browser)
        │
        ▼
  Web app ──────────────► API server
        │                      │
        │                      ├──► Primary database (users, orgs, app data)
        │                      ├──► Cache & events (sessions, real-time bus)
        │                      └──► Analytics store (traces & metrics)
        │
        └──► Live updates (streaming / WebSocket / SSE where needed)
```

At a high level: people use the **web app**, the **API** enforces tenant and auth rules, **agents** run behind the API, and **traces and test results** are stored for later review.

---

## Project status

| Milestone | Focus | Status |
|-----------|--------|--------|
| **M1** | Project skeleton, Docker, health checks | ✅ Done |
| **M2** | Database schema + Alembic migrations | ✅ Done |
| **M3** | Auth core (register/login/logout, JWT, `/me`) | ✅ Done |
| **M4–M6** | Session, orgs, RBAC | Planned |
| **M7–M12** | Providers, traces, agents, HITL, testing | Planned |
| **M13–M15** | Product UI (auth, chat/trace, test runner) | Planned |

Full breakdown: [docs/spec/sprint-plan.md](docs/spec/sprint-plan.md)  
Auth & tenancy design: [docs/spec/auth-spec.md](docs/spec/auth-spec.md)  
Architecture diagrams: [docs/diagrams/](docs/diagrams/)

---

## Get started locally

**Requirements:** [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

From the **repository root**:

```bash
docker compose --env-file .env.example -f docker-compose.dev.yml up --build
```

Then open:

| What | URL |
|------|-----|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (dev) | http://localhost:8000/docs |

The home page should show a green **backend health** indicator when everything is up.

Stop the stack: `Ctrl+C`, then optionally:

```bash
docker compose -f docker-compose.dev.yml down
```

**Note:** `.env.example` ships with safe placeholders for local dev. For real secrets (JWT keys, email, LLM API keys), copy to `.env` and edit — see [Technical details](#technical-details).

Optional dev tools (pgAdmin, Redis Commander):

```bash
docker compose --env-file .env.example -f docker-compose.dev.yml --profile tools up -d
```

---

## Roadmap

Development is **milestone-based**: each phase produces something runnable and testable before the next starts.

High-level sequence: **infrastructure → auth & tenants → agent runtime & traces → HITL & testing → UI**.

Details and time estimates: [docs/spec/sprint-plan.md](docs/spec/sprint-plan.md).

---

## Contributing & documentation

- Specifications live under `docs/spec/`.  
- Diagrams (C4, sequences, ER, flows) live under `docs/diagrams/`.  
- Issues and PRs: use clear descriptions tied to a milestone when possible.

---

## Technical details

### Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Python 3.12 |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Primary database | PostgreSQL 16 |
| Cache / event bus | Redis 7 |
| Trace & metrics storage | ClickHouse 24 |

### Repository layout

```text
├── backend/          # API (FastAPI)
├── frontend/         # Web app (Next.js, src/app)
├── docs/
│   ├── spec/         # auth-spec, sprint-plan
│   └── diagrams/     # architecture & flow diagrams
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.example
```

### Environment variables

```bash
cp .env.example .env   # recommended when adding real secrets
```

Important groups:

- **Postgres / ClickHouse** — database credentials  
- **JWT (RS256)** — required for auth (M3+); generate with OpenSSL (see [m3-auth-core.md](docs/spec/m3-auth-core.md#rs256-key-üretimi))  
- **Resend** — transactional email (verification, invites, password reset)  
- **OpenAI / Anthropic / Ollama** — model providers for agent milestones  

For compose variable substitution (Postgres, ClickHouse service env), either keep `.env` at the repo root or pass `--env-file .env.example` on every `docker compose` command.

### Run without Docker (optional)

**Backend**

```bash
cd backend
pip install uv
uv pip install -e ".[dev]"
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` if the API is not on the default host.

### Database migrations and M2 verification (repo root)

Dev stack (first time, or after `backend/pyproject.toml` dependency changes):

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

Apply migrations only:

```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

**M2 health check** — run all three from the repository root; each command validates one layer. Full explanations and expected output: [docs/spec/m2-db-schema.md — M2 Doğrulama](docs/spec/m2-db-schema.md#m2-doğrulama-repo-kökünden).

```bash
# 1. Migration roundtrip (Alembic downgrade base → upgrade head)
docker compose -f docker-compose.dev.yml exec backend sh -c "alembic downgrade base && alembic upgrade head"

# 2. Model metadata (no DB required)
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/ -v

# 3. Live PostgreSQL schema (8 tables, alembic head, partial unique index)
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/ -v -m integration
```

All three must pass with no errors for M2 to be considered complete.

### M3 verification (repo root)

Dev stack must be running. Details: [docs/spec/m3-auth-core.md — M3 Doğrulama](docs/spec/m3-auth-core.md#m3-doğrulama-repo-kökünden).

```bash
# 1. M3 auth unit tests (password, JWT, token_store, auth_context, deps)
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/test_m3_services.py -v

# 2. All unit tests
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/ -v

# 3. Auth integration tests (register → login → /me → logout)
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/test_auth_flow.py -v -m integration

# 4. Auth smoke (manual)
curl http://localhost:8000/health
curl http://localhost:8000/auth/me
# → 401 without cookie; 200 after login with cookie
```

### Health check

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0","env":"development"}
```

### Compose files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Default stack |
| `docker-compose.dev.yml` | Dev: hot reload, `npm run dev`, optional `--profile tools` |

---

## License

See [LICENSE](LICENSE).
