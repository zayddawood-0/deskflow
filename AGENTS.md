# AGENTS.md — DeskFlow Project Rules

## Project overview (5 lines)

DeskFlow is a full-stack IT helpdesk & ticketing system: employees raise support tickets, agents work them through a status workflow with SLA timers, and admins manage users/categories/SLA policies with an audit log and analytics dashboard. It is a screening project for the ETL Full Stack Web Developer internship, due **Monday 19 October 2026**, built by one developer + an AI agent in ~1 day. Monorepo: `/frontend` (Next.js App Router + TypeScript), `/backend` (FastAPI + SQLAlchemy 2.0 + PostgreSQL), `/docs` (single source of truth). Three roles: `requester`, `agent`, `admin` (RBAC enforced on backend AND frontend). Everything ships through GitHub Actions CI/CD to Neon (DB) and Vercel (API + web, two projects).

## Tech stack (fixed — do not change)

| Layer | Stack |
|---|---|
| Frontend | Next.js (App Router, stable) · React · TypeScript (strict) · Tailwind CSS · shadcn/ui-style components (Radix primitives + cva) · TanStack Query · React Hook Form + Zod · Recharts · lucide-react · Manrope via `next/font` |
| Backend | Python 3.12 · FastAPI · **SQLAlchemy 2.0 sync** (psycopg2) · Pydantic v2 · Alembic · PyJWT · argon2-cffi · slowapi (login rate limit) · pytest + httpx TestClient · ruff |
| Database | PostgreSQL 16 (local via Docker Compose, prod on Neon) |
| Deploy | CI: GitHub Actions (ruff, pytest, next lint/tsc/build). CD: Alembic → Neon, Vercel CLI → API + web |

Sync SQLAlchemy is a deliberate choice (see `docs/ARCHITECTURE.md` → Key decisions). **Never mix async DB code into this repo.**

## Folder structure

```
/
├── frontend/                 # Next.js app (App Router, src/ inside)
│   ├── src/app/              # routes, route groups (auth)/(app)
│   ├── src/components/ui/    # design-system primitives (Button, Card, StatusPill…)
│   ├── src/components/layout/# Navbar, IconRail, TabNav, NotificationBell
│   ├── src/lib/              # api-client.ts, auth.ts, utils.ts, constants.ts
│   ├── src/hooks/            # TanStack Query hooks (use-tickets.ts …)
│   ├── src/schemas/          # Zod schemas
│   └── src/types/            # TS types mirroring API_SPEC.md
├── backend/
│   ├── app/api/v1/routers/   # HTTP layer only (validation + DI + calls service)
│   ├── app/services/         # business logic (state machine, SLA, assignment, audit)
│   ├── app/repositories/     # all SQL queries live here
│   ├── app/models/           # SQLAlchemy models (mirror docs/DATABASE_SCHEMA.md)
│   ├── app/schemas/          # Pydantic request/response models
│   ├── app/core/             # config, security, deps, errors, rate_limit, logging
│   ├── app/db/               # session.py, base.py, seed.py
│   ├── alembic/              # migrations (versions/ + env.py)
│   └── tests/                # pytest suites + conftest.py
├── docs/                     # SOURCE OF TRUTH (see rules below)
├── .github/workflows/        # ci.yml, deploy.yml
├── docker-compose.yml
├── README.md
└── AGENTS.md                 # this file
```

## Coding conventions

### Python / backend
- `ruff check .` and `ruff format .` must pass before any task is called done. Line length 100.
- Full type hints on every function signature (params + return). Pydantic v2 syntax (`model_config`, `field_validator`) — never v1 APIs.
- Layering is strict: `router → service → repository → model`. Routers never touch SQLAlchemy; services never build HTTP responses; repositories never contain business rules.
- Every service mutation **must** write an audit entry via `audit_service.record(...)` (`docs/WORKFLOWS.md` → audit actions list).
- All timestamps are timezone-aware UTC (`datetime.now(timezone.utc)`). Never store naive datetimes.
- Enums are exactly as defined in `docs/DATABASE_SCHEMA.md`: statuses `OPEN | IN_PROGRESS | ON_HOLD | RESOLVED | CLOSED | REOPENED`, priorities `LOW | MEDIUM | HIGH | CRITICAL`, roles `requester | agent | admin`, SLA states `ON_TRACK | AT_RISK | BREACHED` (computed, never stored).
- Errors: raise typed app exceptions from `app/core/errors.py`; never leak stack traces or raw SQL errors to clients.
- No secrets in code — everything via `app/core/config.py` settings (`pydantic-settings`).

### TypeScript / frontend
- `tsconfig.json` has `"strict": true`. **No `any`** — use `unknown` + narrowing or a declared type from `src/types/api.ts`.
- Component files: `PascalCase.tsx`, one component per file; hooks `use-kebab-case.ts`; non-component modules `kebab-case.ts`.
- Server components by default; add `"use client"` only when the component uses state/effects/events.
- All server state goes through TanStack Query hooks in `src/hooks/` — components never call `fetch` directly. The only place raw HTTP happens is `src/lib/api-client.ts`.
- All forms: React Hook Form + Zod schema from `src/schemas/`. Zod schema is the single validation source for forms; backend re-validates regardless.
- Styling only via Tailwind classes using design tokens from `docs/DESIGN_SYSTEM.md`. No inline style objects, no new hex colors outside the token list.
- Enums/constants on the frontend must be imported from `src/lib/constants.ts` and must match the backend values character-for-character.

## How to run locally

```bash
# 1. Database (only infra in Docker)
docker compose up -d db

# 2. Backend  → http://localhost:8000  (docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.db.seed          # demo data + users
uvicorn app.main:app --reload --port 8000

# 3. Frontend → http://localhost:3000
cd frontend
npm install
cp .env.example .env.local
npm run dev

# Or everything at once:
docker compose up --build
```

## How to run tests / checks

```bash
# Backend (DATABASE_URL must point at the test DB; conftest creates schema)
cd backend && ruff check . && ruff format --check . && pytest -q

# Frontend
cd frontend && npm run lint && npm run typecheck && npm run build
```

CI runs exactly these commands — if CI is red, the task is not done.

## Commit message convention

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): short imperative summary`

- types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `style`
- scopes: `backend`, `frontend`, `docs`, `ci`, `db`, `config`
- Examples: `feat(backend): add status transition state machine`, `fix(frontend): SLA countdown ticks off by one`, `docs: align endpoint names with API_SPEC`
- One logical change per commit. Never commit `.env`, `node_modules/`, `.venv/`, `__pycache__/`.

## Definition of done (any task)

A task is done only when **all** of the following are true:
1. Code is written and wired end-to-end (endpoint + service + repository + model/migration + hook + page if applicable).
2. Behavior matches the spec in `/docs` — if the implementation had to differ, the doc is updated in the same commit.
3. New/changed endpoints have tests in `backend/tests/` and pass.
4. `ruff check .` + `pytest -q` (backend) and `npm run lint` + `npm run typecheck` + `npm run build` (frontend) all pass locally.
5. No secrets, no `.env` files, no debug `print()`/`console.log` left behind.
6. The task is ticked off in `docs/IMPLEMENTATION_PLAN.md`.

## Rules

- **`/docs` is the single source of truth.** If code and docs disagree, the docs win until the docs are deliberately edited. Any behavior change (endpoint, field, enum, env var, route, workflow) requires updating the relevant file(s) in `/docs` in the same session.
- **Always check `docs/IMPLEMENTATION_PLAN.md` first** when a session starts: read the current phase, tick off completed tasks as you finish them, and work only the next unticked task unless told otherwise.
- Never rename tables, columns, endpoints, env vars, or components that are referenced in `/docs` without updating every referencing doc.
- Scope guard: anything in the "Cut list" (`docs/IMPLEMENTATION_PLAN.md`) or marked **stretch** is not allowed until all MVP phases are ticked.
- Ask before: changing the tech stack, adding new third-party services, deleting docs files, or touching GitHub secrets/deploy config outside of a deployment task.
