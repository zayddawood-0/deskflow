# DeskFlow — IT Helpdesk & Ticketing System

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](.github/workflows/ci.yml)
[![Backend](https://img.shields.io/badge/backend-FastAPI_%2B_SQLAlchemy-black)](backend/)
[![Frontend](https://img.shields.io/badge/frontend-Next.js_%2B_TypeScript-black)](frontend/)
[![Database](https://img.shields.io/badge/database-PostgreSQL_16-336791)](docs/DATABASE_SCHEMA.md)

**DeskFlow** is a full-stack IT helpdesk & ticketing system. Employees raise support tickets, agents work them through an enforced status workflow with SLA timers that pause while a ticket is on hold, and every important action is written to an immutable audit trail. Three roles (`requester`, `agent`, `admin`) are enforced on the backend and on the frontend.

Built as a screening project for the **ETL Full Stack Web Developer internship** — designed, built and deployed end-to-end in a single day.

> **Pitch:** most small companies track IT support in a shared inbox or a spreadsheet. DeskFlow gives them the essentials of a real ticketing platform — role-based access, an enforced workflow, SLA timers that pause when a ticket is on hold, and a complete audit trail — behind a clean, fast ticket queue.

## Live

| App | URL |
|---|---|
| Web (Vercel — `deskflow-web`) | **https://deskflow-web-ten.vercel.app** |
| API (Vercel — `deskflow-api`, Python serverless) | **https://deskflow-api-five.vercel.app** |
| API docs (Swagger) | **https://deskflow-api-five.vercel.app/docs** |

Both are Vercel projects (root directories `frontend/` and `backend/`) deployed exclusively through GitHub Actions + the Vercel CLI. The API is a serverless function that idles to zero, so the first request after a period of inactivity can take a few seconds to wake.

## What's built — and what isn't

This is an honest status, not a wish list. **Backend** = the endpoint/service + tests exist and are deployed; **Web UI** = a reviewer can do it in the browser today.

### Shipped (live now)

| Area | Backend | Web UI | Notes |
|---|---|---|---|
| Auth — register, login, refresh, logout, change password | ✅ | ✅ | JWT access token held in memory + `httpOnly` refresh cookie; argon2 password hashing |
| RBAC — `requester` / `agent` / `admin` | ✅ | ✅ | enforced per endpoint (`require_roles`) and per route (`RoleGuard`) |
| Tickets — create, list, detail, edit | ✅ | ✅ | API filters: status, priority, category, assignee, unassigned, SLA state + search, sort, pagination. The list UI exposes role tabs, status/priority/sort filters, search and pagination |
| Status workflow | ✅ | ✅ | `OPEN → IN_PROGRESS ⇄ ON_HOLD → RESOLVED → CLOSED`, plus `REOPENED`; invalid transitions return `409` |
| SLA engine | ✅ | ✅ | per-priority first-response & resolution targets, pause/resume math, `ON_TRACK / AT_RISK / BREACHED`, automatic breach flag + notification rows |
| Assignment | ✅ | ✅ | least-loaded auto-assign on creation, agent self-assign, admin assign/unassign |
| Comments & internal notes | ✅ | ✅ | public comments + agent/admin-only internal notes; requesters never receive internal notes on any read path; the first public agent/admin comment sets `first_responded_at`; thread UI with a Public/Internal toggle (internal notes shown with an amber tint) |
| Audit trail | ✅ | ✅ (per ticket) | append-only — a DB trigger rejects `UPDATE`/`DELETE`; per-ticket timeline in the UI, global list via `GET /api/v1/audit` |
| Users admin API | ✅ | ❌ | list / create / get / update / deactivate; self-demotion blocked → no admin screen yet |
| Categories API | ✅ | ❌ | read for all, write for admins |
| SLA policy API | ✅ | ❌ | read for all, update for admins |
| Seed data | ✅ | — | 9 users, 6 categories, 4 SLA policies, 40 tickets spanning 45 days (comments, internal notes, audit, notifications, 9 breached, 5 at-risk, 5 paused) |

### Not built yet

- **Dashboard** (KPI cards, tickets-per-day chart, SLA trend, breakdowns) — neither the `GET /api/v1/dashboard/stats` endpoint nor the page exists.
- **Notifications** — the service writes notification rows (assignments, comments, SLA flags), but there is no notifications API and no bell UI yet.
- **Admin web pages** (users, categories, SLA policies) — APIs only, no screens.
- **Global audit-log page** — the API exists; only the per-ticket timeline is rendered.
- **Live ticking SLA countdowns** and the 30-second notification poll.

## Demo credentials

Seeded by `python -m app.db.seed` (already applied in production):

| Role | Email | Password | Use for |
|---|---|---|---|
| Admin | `admin@deskflow.dev` | `Admin@1234` | Manage users, categories and SLA policies (API / Swagger today) |
| Agent | `agent1@deskflow.dev` | `Agent@1234` | Queue, assignment, status workflow, SLA timers |
| Agent | `agent2@deskflow.dev` · `agent3@deskflow.dev` | `Agent@1234` | Least-loaded auto-assign demo |
| Requester | `requester1@deskflow.dev` | `Requester@1234` | Raise tickets, view own queue |
| Requester | `requester2@deskflow.dev` … `requester5@deskflow.dev` | `Requester@1234` | Additional requesters |

The seed also creates 6 categories (Hardware, Software, Network, Access & Accounts, Email, Other) and ~40 tickets across every status and priority with comments, notes, audit entries, SLA pauses, at-risk and breached tickets — so the queue and the database look alive on first login.

## Architecture

```mermaid
flowchart LR
    subgraph Client
        B[Browser<br/>Next.js on Vercel<br/>server + client components]
    end
    subgraph Server
        A[FastAPI on Vercel<br/>Python serverless · sin1 · NullPool<br/>/api/v1 · routers → services → repositories]
    end
    DB[(PostgreSQL 16<br/>Neon in prod · Docker locally)]
    B -- "same-origin /api/v1/* (Bearer JWT in memory<br/>+ httpOnly refresh cookie)" --> A
    A -- SQLAlchemy 2.0 sync --> DB
    GH[GitHub Actions] -- CI: ruff, pytest, lint, tsc, build --> B & A
    GH -- CD: alembic upgrade head → Neon, vercel deploy --prod (API, then web) --> A & B
    GH -- "Scheduled */15 min: health ping + SLA scan" --> A
```

- **Request flow:** a Next.js page (server component) or client hook → `src/lib/api-client.ts` attaches `Authorization: Bearer <access_token>` → the request goes **same-origin** to `/api/v1/*` and is proxied server-side (Next.js `rewrites()` via `BACKEND_URL`) to FastAPI, which validates input + permissions → service (business rules, state machine, SLA, audit) → repository (SQL) → PostgreSQL. The refresh token never touches JS — it lives in an `httpOnly` cookie scoped to `/api/v1/auth`.
- **Layering is strict:** `router → service → repository → model`. Routers never touch SQLAlchemy; services never build HTTP responses.
- Full details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript (strict), Tailwind CSS, shadcn/ui-style components (Radix + cva), TanStack Query, React Hook Form + Zod, lucide-react, Manrope |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic, PyJWT, argon2-cffi, slowapi |
| Database | PostgreSQL 16 |
| CI/CD | GitHub Actions → Neon (migrations) + Vercel (API + web, via CLI) |
| Local infra | Docker Compose (Postgres only) |

> Recharts is listed in the design docs for the dashboard, but the dashboard isn't built yet, so it isn't a runtime dependency.

## CI/CD pipeline

Order of operations: **CI → migrate → Vercel API → Vercel web**, plus a scheduled scan.

1. **CI** — `.github/workflows/ci.yml`, on push and pull request to `main`:
   - **backend job** — `ruff check .`, `ruff format --check .`, `pytest` against a Postgres 16 service container (a `deskflow_test` database is created first).
   - **frontend job** — `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`.
2. **Deploy** — `.github/workflows/deploy.yml`, triggered when CI completes on `main`; jobs run strictly in order (`needs:`):
   - **migrate** — `alembic upgrade head` against Neon using the **direct** connection string (`NEON_DATABASE_URL`).
   - **Vercel API** — `vercel pull && vercel build --prod && vercel deploy --prebuilt --prod` → `deskflow-api` (`backend/`, region `sin1`, pooled Neon URL + SQLAlchemy `NullPool`).
   - **Vercel web** — same Vercel CLI flow → `deskflow-web` (`frontend/`, `BACKEND_URL = ${{ vars.API_BASE_URL }}`).
3. **Scheduled** — `.github/workflows/scheduled.yml`, every 15 minutes:
   - keep-warm `GET /api/v1/health` (`database: "up"`);
   - `POST /api/v1/internal/sla-scan` with the `X-Internal-Token` header — flags newly breached tickets (idempotently) and writes `SLA_BREACHED` audit entries.

Full setup guide (Neon/Vercel, every secret and variable, rollback, post-deploy smoke test): [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Local setup

### Prerequisites

- Docker + Docker Compose
- Python 3.12, Node.js 20+

### Option A — everything in Docker

```bash
git clone https://github.com/<you>/deskflow.git
cd deskflow
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
docker compose up --build
# frontend → http://localhost:3000 · API → http://localhost:8000 · Swagger → http://localhost:8000/docs
```

### Option B — Docker for the DB only (recommended for development)

```bash
# 1. Database
docker compose up -d db

# 2. Backend (http://localhost:8000)
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.db.seed              # demo data + users
uvicorn app.main:app --reload --port 8000

# 3. Frontend (http://localhost:3000) — new terminal
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Log in with any demo credential from the table above.

## Environment variables

Full reference: [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md).

### Backend — `backend/.env`

| Variable | Purpose | Example (local) |
|---|---|---|
| `APP_ENV` | `development` \| `production` | `development` |
| `SECRET_KEY` | JWT signing secret (≥32 chars random) | `change-me-to-a-long-random-string` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `14` |
| `DATABASE_URL` | SQLAlchemy DB URL | `postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow` |
| `CORS_ORIGINS` | Allowed origins — only for direct-to-API testing (the app goes same-origin through the Next rewrite proxy) | `http://localhost:3000` |
| `SLA_AT_RISK_THRESHOLD` | Fraction of SLA used that means AT_RISK | `0.75` |
| `REOPEN_WINDOW_DAYS` | Days after CLOSED during which a ticket can be reopened | `7` |
| `INTERNAL_TASK_TOKEN` | `X-Internal-Token` required by `POST /api/v1/internal/sla-scan` | `local-internal-token` |
| `LOG_LEVEL` | `DEBUG` \| `INFO` \| `WARNING` | `INFO` |

### Frontend — `frontend/.env.local`

| Variable | Purpose | Example (local) |
|---|---|---|
| `BACKEND_URL` | Server-side origin of the API, consumed by the `/api/:path*` rewrite in `next.config.ts` (never sent to the browser) | `http://localhost:8000` |
| `NEXT_PUBLIC_APP_NAME` | Display name | `DeskFlow` |

## Testing

```bash
# Backend — lint + format check + test suite (runs against Postgres)
cd backend
ruff check . && ruff format --check .
pytest -q --cov=app --cov-report=term-missing

# Frontend — lint + type-check + production build
cd frontend
npm run lint && npm run typecheck && npm run build
```

The suites cover auth, RBAC denials, every valid/invalid status transition, SLA pause/resume/breach math, auto-assignment, comments (including internal-note visibility) and the internal SLA scan ([`backend/tests/`](backend/tests/)); the catalogue lives in [`docs/TESTING.md`](docs/TESTING.md). CI runs the exact same commands on every push and pull request.

## Project structure

```
deskflow/
├── frontend/                 # Next.js app (App Router)
├── backend/                  # FastAPI app + Alembic migrations + tests
├── docs/                     # PRD, architecture, schema, API spec, workflows, plans…
├── .github/workflows/        # ci.yml, deploy.yml, scheduled.yml (cron)
├── docker-compose.yml        # Postgres (+ optional full stack)
├── README.md
└── AGENTS.md                 # AI-agent project rules
```

Docs index (source of truth — kept in sync with the code):

| Doc | What it defines |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | Product requirements, user stories, acceptance criteria |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, layering, cross-cutting concerns |
| [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) | ERD + every table, column, index, enum |
| [`docs/API_SPEC.md`](docs/API_SPEC.md) | Every REST endpoint with request/response schemas |
| [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) | Status state machine, SLA math, auto-assignment |
| [`docs/AUTH_AND_SECURITY.md`](docs/AUTH_AND_SECURITY.md) | JWT flow, RBAC matrix, OWASP checklist |
| [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) | Design tokens + component specs |
| [`docs/FRONTEND_SPEC.md`](docs/FRONTEND_SPEC.md) | Routes, pages, hooks, folder layout |
| [`docs/BACKEND_SPEC.md`](docs/BACKEND_SPEC.md) | Backend structure, services, seed, Alembic |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy + concrete test list |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | CI/CD, Neon/Vercel, secrets |
| [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) | Every env var + `.env.example` contents |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Time-boxed build plan |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | 3–5 minute reviewer walkthrough |

## What I'd build next

In priority order — finishing the partially-built surfaces first, then the stretch list:

**Finish the partial surfaces**

1. **Dashboard** — `GET /api/v1/dashboard/stats` + `/dashboard`: KPI cards, tickets-per-day, SLA compliance trend, breakdowns, recent tickets.
2. **Notifications** — `/notifications` endpoints (list, unread count, mark read) + the bell with 30 s polling.
3. **Admin pages** — `/admin/users`, `/admin/categories`, `/admin/sla` over the existing APIs.
4. **Global audit page** — `/audit` with URL-synced filters over `GET /api/v1/audit`.

**Stretch**

5. **File attachments** on tickets and comments (S3-compatible storage + signed URLs).
6. **Email notifications** for assignment, comments and SLA warnings.
7. **WebSocket live updates** replacing notification polling.
8. **CSV export** of tickets and the audit log.
9. **Dark mode** driven by the design-token layer.
10. **SLA calendars** (pause targets outside business hours) and per-category SLA overrides.
11. **Saved views / filters** and saved dashboard report ranges.

## License

MIT
