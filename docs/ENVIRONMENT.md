# Environment variables — DeskFlow

Two env files, both git-ignored; the committed templates are `backend/.env.example` and `frontend/.env.example`.

## 1. Backend (`backend/.env`)

| Name | Purpose | Required | Local example | Production value |
|---|---|---|---|---|
| `APP_ENV` | `development` \| `production` (gates fail-fast startup checks, e.g. requiring a strong `SECRET_KEY`) | no (default `development`) | `development` | `production` (deskflow-api Vercel env) |
| `SECRET_KEY` | HS256 signing key for access tokens (≥ 32 random chars) | **yes** | `local-dev-secret-change-me-0123456789abcdef` | random 64-char string (deskflow-api Vercel env) |
| `ALGORITHM` | JWT algorithm | no (`HS256`) | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes | no (`30`) | `30` | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime in days | no (`14`) | `14` | `14` |
| `DATABASE_URL` | SQLAlchemy URL `postgresql+psycopg2://user:pass@host:port/db` (+`?sslmode=require` remote) | **yes** | `postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow` | Neon **pooled** string (`-pooler` host; deskflow-api Vercel env). Migrations use the separate GitHub secret `NEON_DATABASE_URL` (Neon **direct** endpoint) |
| `CORS_ORIGINS` | Comma-separated allowed origins — **only for direct-to-API testing** (the browser app goes same-origin through the Next rewrite proxy; prod needs none) | no (`http://localhost:3000`) | `http://localhost:3000` | *(unset)* |
| `SLA_AT_RISK_THRESHOLD` | Fraction of an SLA target that means `AT_RISK` | no (`0.75`) | `0.75` | `0.75` |
| `REOPEN_WINDOW_DAYS` | Days after `CLOSED` during which `CLOSED→REOPENED` is allowed | no (`7`) | `7` | `7` |
| `INTERNAL_TASK_TOKEN` | Shared token required by `POST /api/v1/internal/sla-scan` (`X-Internal-Token` header) — must equal the GitHub secret of the same name used by `scheduled.yml` | no (default local literal) | `local-internal-token` | random string (deskflow-api Vercel env **and** GitHub secret, identical values) |
| `LOG_LEVEL` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` | no (`INFO`) | `DEBUG` | `INFO` |
| `APP_VERSION` | Reported by `/api/v1/health` (optional override of the baked default `1.0.0`) | no | `1.0.0` | `1.0.0` |

Notes:
- `session.py` normalizes `DATABASE_URL` in a **pure function**: `postgres://` → `postgresql+psycopg2://`, and `sslmode=require` added when the host is not `localhost`. An empty/missing URL raises a clear `DATABASE_URL is required and must not be empty` error at startup instead of a cryptic SQLAlchemy parse error.
- On Vercel (detected via the `VERCEL=1` env var the runtime sets), SQLAlchemy uses **`NullPool`**: no persistent connection pool on an ephemeral serverless instance — connections are opened per session and closed with it ([DEPLOYMENT §9](DEPLOYMENT.md#9-serverless-notes-vercel-python-runtime)).
- Startup fails fast when `APP_ENV=production` and `SECRET_KEY` is missing or < 32 chars.
- Login/register rate limiting (`slowapi`) uses **in-memory storage** — per-process, and on Vercel per warm lambda instance. Best-effort by design (never crashes, exact locally and under light traffic); a shared store is a deliberate cut.
- CI supplies `DATABASE_URL` and `TEST_DATABASE_URL` (both on the Postgres service container — `TEST_DATABASE_URL` points at a separate `deskflow_test` database created before pytest) and `SECRET_KEY` inline — no `.env` file in CI. `TEST_DATABASE_URL` is test-only (never read by the app) and is what `conftest.py` uses to run migrations/tests, keeping them off the app database.

### `backend/.env.example` (committed template)

```dotenv
# DeskFlow backend — copy to .env and adjust
APP_ENV=development
SECRET_KEY=local-dev-secret-change-me-0123456789abcdef
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14

# Postgres from docker compose (docker compose up -d db)
DATABASE_URL=postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow

CORS_ORIGINS=http://localhost:3000
SLA_AT_RISK_THRESHOLD=0.75
REOPEN_WINDOW_DAYS=7
INTERNAL_TASK_TOKEN=local-internal-token
LOG_LEVEL=DEBUG
```

## 2. Frontend (`frontend/.env.local`)

| Name | Purpose | Required | Local example | Production value |
|---|---|---|---|---|
| `BACKEND_URL` | **Server-side** origin of the FastAPI backend, consumed by `next.config.ts` `rewrites()` (`/api/:path*` → `${BACKEND_URL}/api/:path*`). Never exposed to the browser (`NEXT_PUBLIC_`-free) | **yes** | `http://localhost:8000` | deskflow-api production origin, e.g. `https://deskflow-api.vercel.app` (deskflow-web Vercel env + GitHub variable `API_BASE_URL`, same value) |
| `NEXT_PUBLIC_APP_NAME` | Display name in the navbar/toasts | no (`DeskFlow`) | `DeskFlow` | `DeskFlow` |

Rules:
- The browser only ever requests **same-origin `/api/v1/*`**; the rewrite proxy performs the Vercel→Vercel hop server-side, which is why no CORS configuration and no cross-site cookie handling are needed.
- `BACKEND_URL` must be an **origin only** (no trailing `/api/v1`).
- Set `BACKEND_URL` in Vercel → deskflow-web → Settings → Environment Variables (Production/Preview/Development); `vercel pull` makes it available to `next.config.ts` during the CI build. The deploy workflow additionally passes `BACKEND_URL=${{ vars.API_BASE_URL }}` — keep the repo variable and the Vercel env var identical.

### `frontend/.env.example` (committed template; copy to `.env.local`)

```dotenv
# DeskFlow frontend — copy to .env.local
# Server-side API origin consumed by the /api/:path* rewrite (no trailing slash, no /api/v1)
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=DeskFlow
```

## 3. Where each variable lives

| Context | Backend vars | Frontend vars |
|---|---|---|
| Local dev | `backend/.env` (from `.env.example`) | `frontend/.env.local` (from `.env.example`) |
| Local Docker Compose | inline in `docker-compose.yml` `environment:` | inline `BACKEND_URL: http://backend:8000` (compose service name) |
| CI (`ci.yml`) | inline job `env:` (dev + test DB URLs + dummy secret/token) | none — `next.config.ts` falls back to `http://localhost:8000` when `BACKEND_URL` is unset (build only needs the rewrite table to exist) |
| Production | Vercel **deskflow-api** project env vars (`APP_ENV`, `SECRET_KEY`, `DATABASE_URL` = Neon pooled, `INTERNAL_TASK_TOKEN`, thresholds; `CORS_ORIGINS` unset) | Vercel **deskflow-web** project env vars (`BACKEND_URL`, `NEXT_PUBLIC_APP_NAME`) |
| CD pipeline | GitHub Actions secrets (`NEON_DATABASE_URL`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_API`, `VERCEL_PROJECT_ID_WEB`, `INTERNAL_TASK_TOKEN`) + repo variable `API_BASE_URL` — pipeline-only, never app runtime | same |

Setup steps for the production services: [DEPLOYMENT §2–§4](DEPLOYMENT.md#2-neon-production-database).
