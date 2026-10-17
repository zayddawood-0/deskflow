# DeskFlow — IT Helpdesk & Ticketing System

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](.github/workflows/ci.yml)
[![Backend](https://img.shields.io/badge/backend-FastAPI_%2B_SQLAlchemy-black)](backend/)
[![Frontend](https://img.shields.io/badge/frontend-Next.js_%2B_TypeScript-black)](frontend/)
[![Database](https://img.shields.io/badge/database-PostgreSQL_16-336791)](docs/DATABASE_SCHEMA.md)

**DeskFlow** is a full-stack IT helpdesk & ticketing system. Employees raise support tickets, agents work them through a status workflow with live SLA timers, and admins manage users, categories and SLA policies while monitoring an immutable audit log and an analytics dashboard.

Built as a screening project for the **ETL Full Stack Web Developer internship** — designed, built and deployed end-to-end in a single day.

> **Pitch:** most small companies track IT support in a shared inbox or a spreadsheet. DeskFlow gives them the essentials of a real ticketing platform — role-based access, an enforced workflow, SLA timers that pause when a ticket is on hold, internal notes, and a complete audit trail — with a clean, modern dashboard that makes the state of IT support obvious in 5 seconds.

---

## Features

- **Auth & RBAC** — email + password login, JWT access & refresh tokens, argon2 password hashing, three roles (`requester`, `agent`, `admin`) enforced on every endpoint and every route.
- **Tickets** — create, list, filter (status, priority, category, assignee, SLA state), full-text search, sort, pagination, detail page.
- **Status workflow** — `OPEN → IN_PROGRESS ⇄ ON_HOLD → RESOLVED → CLOSED`, plus `REOPENED`; enforced server-side as a state machine (invalid transitions → `409`).
- **Priorities** — `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- **Assignment** — manual assignment by admins, self-assign by agents, and auto-assignment to the least-loaded active agent on creation.
- **SLA engine** — per-priority first-response and resolution targets (admin-editable), timers **pause while a ticket is ON_HOLD**, live countdown + `ON_TRACK` / `AT_RISK` / `BREACHED` badges, automatic breach detection & notification.
- **Comments & internal notes** — public conversation with the requester, plus agent-only internal notes.
- **Audit log** — append-only record of every important event with actor, action, old/new value and timestamp; per-ticket timeline + global filterable log.
- **Dashboard** — KPI cards, tickets-per-day bar chart, SLA compliance trend, breakdown by priority/category, recent tickets table.
- **Notifications** — in-app bell: assignment, new comments, SLA at risk / breached.

## Screenshots

> _Screenshots captured after deployment — see `docs/DEMO_SCRIPT.md` for the walkthrough they correspond to._

| Dashboard | Ticket detail |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Ticket](docs/screenshots/ticket-detail.png) |

| Tickets list | Admin — SLA policies |
|---|---|
| ![Tickets](docs/screenshots/tickets.png) | ![SLA](docs/screenshots/admin-sla.png) |

## Live demo

| App | URL |
|---|---|
| Frontend (Vercel) | https://deskflow-web.vercel.app |
| API (Render) | https://deskflow-api.onrender.com |
| API docs (Swagger) | https://deskflow-api.onrender.com/docs |

> Render free tier spins down after inactivity — the first load may take ~30–60 s while the API cold-starts. The frontend shows a "waking up" skeleton and retries automatically.

## Demo credentials

Seeded by `python -m app.db.seed` (also pre-applied in production):

| Role | Email | Password | Use for |
|---|---|---|---|
| Admin | `admin@deskflow.dev` | `Admin@1234` | Dashboard, audit log, user/category/SLA management |
| Agent | `agent1@deskflow.dev` | `Agent@1234` | Queue, assignment, comments, internal notes, SLA timers |
| Agent | `agent2@deskflow.dev` | `Agent@1234` | Second agent (least-loaded auto-assign demo) |
| Agent | `agent3@deskflow.dev` | `Agent@1234` | Third agent |
| Requester | `requester1@deskflow.dev` | `Requester@1234` | Raise tickets, comment, close/reopen own tickets |
| Requester | `requester2@deskflow.dev` … `requester5@deskflow.dev` | `Requester@1234` | Additional requesters |

Seed data also creates 6 categories (Hardware, Software, Network, Access & Accounts, Email, Other) and ~40 tickets spread across every status/priority with comments, notes, audit entries, SLA pauses, at-risk and breached tickets — so the dashboard looks alive on first login.

## Architecture

```mermaid
flowchart LR
    subgraph Client
        B[Browser<br/>Next.js on Vercel<br/>server + client components]
    end
    subgraph Server
        A[FastAPI on Render<br/>/api/v1 · routers → services → repositories]
    end
    DB[(PostgreSQL 16<br/>Neon in prod · Docker locally)]
    B -- "same-origin /api/v1/* (Bearer JWT in memory<br/>+ httpOnly refresh cookie)" --> A
    A -- SQLAlchemy 2.0 sync --> DB
    GH[GitHub Actions] -- CI: ruff, pytest, lint, tsc, build --> B & A
    GH -- CD: alembic upgrade head → Neon, deploy hook → Render, vercel deploy --prod --> A & B
    GH -- "Scheduled */15 min: health ping + SLA scan" --> A
```

- **Request flow:** Next.js page (server component) or client hook → `src/lib/api-client.ts` attaches `Authorization: Bearer <access_token>` → the request goes **same-origin** to `/api/v1/*` and is proxied server-side (Next.js `rewrites()`, `BACKEND_URL`) to FastAPI, which validates input + permissions → service (business rules, state machine, SLA, audit) → repository (SQL) → PostgreSQL. The refresh token never touches JS — it is an httpOnly cookie scoped to `/api/v1/auth`.
- Full details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript (strict), Tailwind CSS, shadcn/ui-style components, TanStack Query, React Hook Form + Zod, Recharts, lucide-react, Manrope |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic, PyJWT, argon2-cffi, slowapi |
| Database | PostgreSQL 16 |
| CI/CD | GitHub Actions → Neon (migrations), Render (API), Vercel (web) |
| Local infra | Docker Compose (Postgres only) |

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
python -m app.db.seed
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
| `INTERNAL_TASK_TOKEN` | `X-Internal-Token` header required by `POST /api/v1/internal/sla-scan` (set by the GitHub scheduled workflow; must match its secret) | `local-internal-token` |
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

Test cases are catalogued in [`docs/TESTING.md`](docs/TESTING.md) (auth, RBAC denials, every valid/invalid status transition, SLA pause/resume/breach math, auto-assignment, internal-note visibility, audit entries). CI runs the exact same commands on every push and pull request.

## Deployment

Push to `main` triggers `.github/workflows/deploy.yml`:

1. **Migrate** — `alembic upgrade head` runs from GitHub Actions against the Neon database (`NEON_DATABASE_URL` secret).
2. **Backend** — a `curl` hits the Render deploy hook (`RENDER_DEPLOY_HOOK_URL`), which rebuilds and redeploys `deskflow-api`.
3. **Frontend** — the Vercel CLI (`vercel pull && vercel build --prod && vercel deploy --prebuilt --prod`) ships `deskflow-web` with `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

Additionally, `.github/workflows/scheduled.yml` runs every 15 minutes: it pings `GET /api/v1/health` (keeps the Render free instance warm) and calls `POST /api/v1/internal/sla-scan` with `X-Internal-Token` (`INTERNAL_TASK_TOKEN` secret) so SLA breaches are flagged and notified even when nobody has the app open — the scan is idempotent, so double runs change nothing.

Full setup guide (Neon/Render/Vercel, all secrets, rollback, post-deploy smoke test): [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

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

Docs index (source of truth — keep in sync with code):

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
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | CI/CD, Neon/Render/Vercel, secrets |
| [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) | Every env var + `.env.example` contents |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Time-boxed build plan |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | 3–5 minute reviewer walkthrough |

## What I'd build next

Given more time, in priority order (all currently on the [stretch list](docs/PRD.md#6-stretch-features-only-after-all-mvp-phases-are-ticked)):

1. **File attachments** on tickets and comments (S3-compatible storage + signed URLs).
2. **Email notifications** via a transactional email API for assignment, comments and SLA warnings.
3. **WebSocket live updates** replacing the 30-second notification poll.
4. **CSV export** of tickets and the audit log.
5. **Dark mode** driven by the design-token layer.
6. **SLA calendars** (pause targets outside business hours) and per-category SLA overrides.
7. **Saved views / filters** and saved dashboard report ranges.

## License

MIT
