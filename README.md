# AI Agent Observatory

Multi-tenant platform for testing, observing, and orchestrating AI agents.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Database | PostgreSQL 16 |
| Cache / Events | Redis 7 |
| Trace Storage | ClickHouse 24 |

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.12+ (for local backend dev)

### 2. Environment Setup

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `POSTGRES_PASSWORD` — set a strong password
- `CLICKHOUSE_PASSWORD` — set a strong password
- `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` — generate below
- `RESEND_API_KEY` — get from resend.com

### 3. Generate JWT Keys

```bash
# Generate private key
openssl genrsa -out private.pem 2048

# Generate public key
openssl rsa -in private.pem -pubout -out public.pem

# Copy contents into .env
# JWT_PRIVATE_KEY="$(cat private.pem)"
# JWT_PUBLIC_KEY="$(cat public.pem)"
```

### 4. Run

```bash
docker compose up
```

Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- ClickHouse: localhost:8123

### 5. Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0","env":"development"}
```

## Development

### Backend (local)

```bash
cd backend
pip install uv
uv pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Frontend (local)

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

### Database Migrations

```bash
cd backend
alembic upgrade head      # Apply migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic downgrade -1      # Rollback one step
```

## Project Structure

```
observatory/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── core/         # Config, DB, Redis, responses
│   │   ├── models/       # SQLAlchemy models
│   │   └── services/     # Business logic
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── alembic/          # DB migrations
│   └── pyproject.toml
├── frontend/
│   ├── app/              # Next.js app router
│   ├── components/
│   └── lib/
├── docs/
│   ├── spec/             # Auth spec, sprint plan
│   └── diagrams/         # Mermaid diagrams
├── docker-compose.yml
└── .env.example
```

## Sprint Plan

See [docs/spec/sprint-plan.md](docs/spec/sprint-plan.md) for the full milestone plan.

Current milestone: **M1 — Project Skeleton** ✅
