# Deployment — DeskFlow

| Env | Frontend | API | Database |
|---|---|---|---|
| **Local** | `next dev` on :3000 (or Docker) | `uvicorn --reload` on :8000 (or Docker) | Postgres 16 in Docker Compose (`db`, port 5432) |
| **Production** | Vercel project **deskflow-web** → `deskflow-web.vercel.app` | Vercel project **deskflow-api** (Python serverless, `sin1`) → `deskflow-api.vercel.app` | Neon (free tier, Postgres 16) |

Same code in both; only env vars differ ([ENVIRONMENT](ENVIRONMENT.md)). Both apps deploy **only** through `deploy.yml` (Vercel CLI) — Vercel's own Git integration is disabled in both `vercel.json` files (`"git": { "deploymentEnabled": false }`).

## 1. Local Docker Compose (`docker-compose.yml`)

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: deskflow-db
    environment:
      POSTGRES_USER: deskflow
      POSTGRES_PASSWORD: deskflow
      POSTGRES_DB: deskflow
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U deskflow -d deskflow"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ./backend
    container_name: deskflow-api
    depends_on:
      db: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql+psycopg2://deskflow:deskflow@db:5432/deskflow
      SECRET_KEY: local-dev-secret-change-me-0123456789abcdef
      APP_ENV: development
      CORS_ORIGINS: http://localhost:3000
    ports:
      - "8000:8000"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    container_name: deskflow-web
    depends_on: [backend]
    environment:
      BACKEND_URL: http://backend:8000   # compose-internal origin for the /api/:path* rewrite
    ports:
      - "3000:3000"

volumes:
  pgdata:
```

Day-to-day development runs **only `db`** in Docker (hot reload for both apps on the host) — see README quick start. `docker compose up --build` runs everything for a clean-machine check.

Dockerfiles: `backend/Dockerfile` (`python:3.12-slim`, `pip install -r requirements.txt`, `uvicorn app.main:app`), `frontend/Dockerfile` (node:20-alpine, `npm ci`, `npm run build`, `npm start`). These are local/Docker conveniences only — production runs on Vercel's Python/Node runtimes.

## 2. Neon (production database)

Neon exposes **two** connection strings per branch; DeskFlow uses both, for different jobs:

| String | Hostname shape | Used by | Stored as |
|---|---|---|---|
| **Direct** (no pooler) | `ep-xxxx-xxxx.ageneon...` | Alembic migrations in the `migrate` job — each migration run is short-lived, and the direct endpoint avoids pooler edge cases with DDL | GitHub secret **`NEON_DATABASE_URL`** |
| **Pooled** (PgBouncer) | `ep-xxxx-xxxx-pooler.ageneon...` | The API at runtime on Vercel — serverless instances are ephemeral, so every request may get a fresh connection; the pooler absorbs that | `DATABASE_URL` env var in the **deskflow-api** Vercel project |

Setup:

1. Create a free account → New project → region **AWS Singapore (ap-southeast-1)** (matches Vercel's `sin1`) → Postgres 16.
2. Copy **both** strings from the dashboard. Format expected by the app:
   `postgresql+psycopg2://USER:PASSWORD@HOST/deskflow?sslmode=require`
   (Neon's dashboard gives `postgres://` — both `session.py` and `alembic/env.py` normalize the scheme via `normalize_database_url`, and `sslmode=require` is appended automatically when missing, but prefer setting the SQLAlchemy-ready form.)
3. Create the GitHub secret **`NEON_DATABASE_URL`** with the **direct** string (CD migrate job only).
4. The pooled string is set as `DATABASE_URL` in the deskflow-api Vercel project (§3) — never in GitHub.
5. Leave the default `main` branch; migrations always run against it. (Rollback uses `alembic downgrade`, §7.)

## 3. Vercel — deskflow-api (FastAPI, Python serverless)

The API runs on Vercel's Python runtime as a serverless function:

- `backend/vercel.json` — `"framework": "fastapi"`, `"regions": ["sin1"]` (same region as Neon), `"git": { "deploymentEnabled": false }` (deploys only via `deploy.yml`).
- `backend/index.py` — the recognized Vercel entrypoint; it re-exports the FastAPI `app` from `app.main`. Vercel's FastAPI preset serves the whole app from this single function (every path: `/api/v1/*`, `/docs`, `/api/v1/health`), with the project root on the import path.
- `requirements.txt` at `backend/` root is installed by Vercel's Python builder, and `backend/.python-version` pins the function to Python `3.12`.
- `app/db/session.py` detects the runtime via the `VERCEL=1` env var Vercel sets and switches SQLAlchemy to **`NullPool`** — no persistent connection pool on an ephemeral instance; connections open per session and close with it, which is the correct shape for serverless + Neon's pooler.

### 3.1 Create the project

1. `cd backend && npx vercel link` → "Set up and deploy?" → yes → scope/team → **Project Name: `deskflow-api`** (or let Vercel suggest the directory name). When asked about disabling Git integration, confirm — `vercel.json` enforces it anyway.
2. `vercel.json` and the entrypoint `index.py` are already committed, so the first production deploy is: `npx vercel deploy --prod` from `backend/` (optional — `deploy.yml` does this on every push to `main`).
3. Project → Settings → Root Directory should read `backend` (set automatically by linking from that directory). If you instead created the project in the dashboard, set Root Directory to `backend` manually and link locally afterwards.

### 3.2 Environment variables (project → Settings → Environment Variables)

| Key | Value | Environments |
|---|---|---|
| `DATABASE_URL` | Neon **pooled** connection string (`-pooler` host, `sslmode=require`) | Production + Preview + Development |
| `SECRET_KEY` | long random string, ≥ 32 chars (Generate button) | Production (+ Preview/Dev can reuse or use separate values) |
| `APP_ENV` | `production` | Production |
| `INTERNAL_TASK_TOKEN` | long random string — **must match the GitHub secret of the same name** (used by `scheduled.yml` → `X-Internal-Token`) | Production |
| `CORS_ORIGINS` | *(leave unset — the browser talks to the API only through the Vercel rewrite proxy)* | — |
| `SLA_AT_RISK_THRESHOLD` / `REOPEN_WINDOW_DAYS` / `LOG_LEVEL` | optional overrides of the defaults (`0.75` / `7` / `INFO`) | Production |

How to create/rotate each: [AUTH_AND_SECURITY §9](AUTH_AND_SECURITY.md#9-secrets-handling).

### 3.3 Gotchas

- `Settings` requires `SECRET_KEY` at import time; with `APP_ENV=production` it must be ≥ 32 chars or the function fails fast at cold start (by design).
- An empty/missing `DATABASE_URL` fails with a clear `DATABASE_URL is required and must not be empty...` error instead of a cryptic SQLAlchemy URL parse error.
- Cold starts are sub-second to a couple of seconds (Python module import + `create_engine` with NullPool — no connection is opened until a request needs one).

## 4. Vercel — deskflow-web (Next.js)

1. `cd frontend && npx vercel link` → **Project Name: `deskflow-web`**. Root Directory: `frontend`. `frontend/vercel.json` already sets `"git": { "deploymentEnabled": false }` — do **not** connect the repo in the dashboard's Git settings.
2. Project → Settings → Environment Variables:
   | Key | Value | Environments |
   |---|---|---|
   | `BACKEND_URL` | the deskflow-api production origin (e.g. `https://deskflow-api.vercel.app` — no trailing slash, no `/api/v1`) | Production + Preview + Development |
   | `NEXT_PUBLIC_APP_NAME` | `DeskFlow` | Production + Preview + Development |
   The browser never calls the API origin directly — `next.config.ts` rewrites `/api/:path*` → `${BACKEND_URL}/api/:path*` on the server, so no CORS wiring is needed.
3. Domain: the generated `*.vercel.app` domain is enough — all browser traffic is same-origin through the rewrite proxy.

## 5. GitHub Actions workflows

### 5.1 `.github/workflows/ci.yml` (every push + PR)

Unchanged from the standard template: backend job (Postgres service container, `ruff check`, `ruff format --check`, `pytest`), frontend job (`npm run lint`, `npm run typecheck`, `npm run build`). See the file itself for the full YAML.

### 5.2 `.github/workflows/deploy.yml` (push to `main`, after CI passes)

```yaml
name: Deploy

on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main]
  workflow_dispatch:

concurrency:
  group: deploy-production
  cancel-in-progress: false

jobs:
  migrate:
    name: Alembic → Neon
    if: ${{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-24.04
    defaults:
      run:
        working-directory: backend
    env:
      DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
      SECRET_KEY: migrate-only-secret-key-not-used-in-prod-0123456789
      APP_ENV: development
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.workflow_run.head_sha || github.sha }}
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - run: alembic upgrade head

  deploy-api:
    name: Vercel — deskflow-api
    needs: migrate
    runs-on: ubuntu-24.04
    defaults:
      run:
        working-directory: backend
    env:
      VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
      VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
      VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID_API }}
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.workflow_run.head_sha || github.sha }}
      - uses: actions/setup-node@v7
        with:
          node-version: 20
      - uses: astral-sh/setup-uv@v10.3.0
        with:
          python-version: "3.12"
      - run: uv python install 3.12
      - run: npx vercel pull --yes --environment=production
      - run: npx vercel build --prod
      - run: npx vercel deploy --prebuilt --prod

  deploy-web:
    name: Vercel — deskflow-web
    needs: deploy-api
    runs-on: ubuntu-24.04
    defaults:
      run:
        working-directory: frontend
    env:
      VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
      VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
      VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID_WEB }}
      BACKEND_URL: ${{ vars.API_BASE_URL }}
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.workflow_run.head_sha || github.sha }}
      - uses: actions/setup-node@v7
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npx vercel pull --yes --environment=production
      - run: npx vercel build --prod
      - run: npx vercel deploy --prebuilt --prod
```

Triggering: `deploy.yml` fires on the **`workflow_run` completion of `ci.yml` on `main`** and only when that CI run concluded `success` (the job-level `if`); it never deploys on red CI. `workflow_dispatch` allows a manual re-deploy. The checkout uses `github.event.workflow_run.head_sha` so the exact commit CI validated is the one migrated/deployed.

How the Vercel CLI jobs work: `vercel pull --yes --environment=production` downloads the project's production env vars (into `.vercel/`, git-ignored) and links to the project identified by `VERCEL_TOKEN` + `VERCEL_ORG_ID` + `VERCEL_PROJECT_ID_*`; `vercel build --prod` builds locally (Python lambda for the API, `next build` for the web app); `vercel deploy --prebuilt --prod` uploads the prebuilt output — no build happens on Vercel's side.

The API job installs **`uv`** (`astral-sh/setup-uv`) before building: Vercel's Python builder uses `uv` to create the function venv and install `requirements.txt`. Vercel's own build image ships `uv`, but the GitHub runner does not — without this step `vercel build` fails with `[UV_ERROR] uv is required but was not found in PATH`. `uv python install 3.12` pre-fetches the interpreter (also pinned in `backend/.python-version`). The web job needs no `uv` — Next.js only.

Why `migrate` sets `SECRET_KEY`/`APP_ENV`: `alembic/env.py` calls `get_settings()` to read `DATABASE_URL`, and `Settings` requires `SECRET_KEY` — so the job must provide one (a throw-away literal is fine; the value is never used to sign anything during a migration) even though the DB URL is the only input that matters. `NEON_DATABASE_URL` is the sole secret this job needs; if it is unset, `DATABASE_URL` resolves to an empty string and Alembic fails immediately with the explicit `DATABASE_URL is required...` error.

Ordering guarantees: **migrations before code** (the new lambda starts against an already-migrated DB; FastAPI is backward-compatible with the previous schema for one release because migrations are additive within a release). The web deploy waits for the API deploy so a newly rewritten frontend never points at an old API build.

> Branch-protection tip: require the CI workflow green before merging to `main` (repo Settings → Branches → `main` → Require status checks).

### 5.3 `.github/workflows/scheduled.yml` (cron every 15 min + manual)

Uptime check + SLA scan. The API URL comes from the **repo variable `API_BASE_URL`** (not a secret — it is public anyway once the app is live):

```yaml
name: Scheduled

on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch:

jobs:
  health-check:
    name: Ping API health
    runs-on: ubuntu-24.04
    env:
      API_BASE_URL: ${{ vars.API_BASE_URL }}
    steps:
      - name: GET /api/v1/health
        run: |
          curl --fail --silent --show-error --max-time 120 \
            "${API_BASE_URL}/api/v1/health"

  sla-scan:
    name: SLA breach / at-risk scan
    runs-on: ubuntu-24.04
    env:
      API_BASE_URL: ${{ vars.API_BASE_URL }}
    steps:
      - name: POST /api/v1/internal/sla-scan
        run: |
          curl --fail --silent --show-error --max-time 120 \
            -X POST \
            -H "X-Internal-Token: ${{ secrets.INTERNAL_TASK_TOKEN }}" \
            "${API_BASE_URL}/api/v1/internal/sla-scan"
```

Notes:
- `INTERNAL_TASK_TOKEN` (GitHub secret) must equal the deskflow-api env var of the same name — the backend compares the `X-Internal-Token` header against it with a constant-time compare.
- The SLA scan is idempotent ([API_SPEC §12](API_SPEC.md#12-internal-apiv1internal)) — double runs never duplicate audit rows or notifications. The same detection also runs on ticket reads/mutations, so the cron scan only catches tickets nobody is looking at.
- A red `health-check` run means the API was unreachable for 2 minutes (an outage, or — rarely — a very slow cold start); a red `sla-scan` run means a bad/missing token, a missing `API_BASE_URL` variable, or a server error — check the run's curl output.
- Cron on the free tier of GitHub Actions can be delayed by several minutes under load; 15-minute granularity is a best-effort cadence, not a hard guarantee.
- Both jobs are plain `curl` — no checkout needed, they run in seconds.

## 6. Migration strategy

- **Source of truth:** `backend/alembic/versions/` — every schema change is a new revision, reviewed in the PR like any code.
- **Production runs:** only through the `migrate` job in `deploy.yml` (`alembic upgrade head` from GitHub Actions with `NEON_DATABASE_URL`, the direct Neon endpoint). The API never runs migrations at boot — serverless cold starts must stay fast and race-free.
- **Rules:**
  1. Additive-first: add columns/tables as nullable or with defaults — the previous app version must keep working during the deploy window.
  2. Never edit an applied revision; fix forward.
  3. Destructive changes (drop/rename) ship in two releases: (a) stop using the old thing + add the new thing, (b) drop later.
  4. The initial migration `0001_initial` also seeds `sla_policies` + the `('ticket', 1040)` counter row idempotently, so a fresh Neon DB matches local.
- **Prod DB bootstrap:** empty Neon DB → first `deploy.yml` run creates the whole schema; then run the seed once manually if demo data is wanted in prod: `gh workflow run deploy.yml` is not enough — run locally `DATABASE_URL=<neon pooled string> python -m app.db.seed`.

## 7. Rollback notes

| Failure | Fix |
|---|---|
| Bad migration detected immediately after merge | `cd backend && DATABASE_URL=$NEON_DATABASE_URL alembic downgrade -1` from a workstation, then ship a fix-forward revision; the running lambdas keep serving the previous code until the next deploy |
| Bad API build | Vercel → deskflow-api → Deployments → promote the previous deployment (instant rollback, no build); no DB change needed for pure-code regressions |
| Bad frontend build | Vercel → deskflow-web → Deployments → promote the previous deployment |
| Both | revert commit on `main` and push; CI/CD redoes the pipeline in the right order |
| `SECRET_KEY` rotated accidentally | all access tokens invalidate; users re-login (refresh tokens keep working — only JWTs die). Communicate as a forced re-login |

## 8. Post-deploy smoke test

Run after every production deploy (also the manual UI regression checklist):

1. `curl https://deskflow-api.vercel.app/api/v1/health` → `{"status":"ok","database":"up","version":"1.0.0"}` (first call may take a few seconds cold).
2. Login as `agent1@deskflow.dev` → dashboard loads, KPI numbers present, charts render.
3. Login as `requester1@deskflow.dev` → `/tickets` lists only own tickets; create a ticket with a `CRITICAL` priority → due dates visible, countdown ticking.
4. Login as agent → new ticket appears (auto-assigned), self-assign a second one, add an internal note, put a third on hold → "Paused" state shown.
5. Transition one to `RESOLVED`; try an invalid transition (`PATCH`-less quick check via Swagger: `OPEN→CLOSED` on some ticket) → 409 with code.
6. Requester reopens the resolved ticket; admin sees both events in `/audit` filtered by that ticket.
7. Bell shows unread items; mark-all-read works.
8. `/admin/sla` save works (revert the change after checking).
9. Console free of errors; mobile width spot-check; Network tab shows all API calls going to the same origin (`/api/v1/*`, i.e. the deskflow-web domain — never direct to the API origin).

## 9. Serverless notes (Vercel Python runtime)

- **Cold starts:** an idle lambda scales to zero; the first request pays the Python import + `create_engine` cost (typically well under a second to a couple of seconds). No connection is opened at import — `NullPool` means connections are created per request and released with the session, so cold starts never block on the DB.
- **Login rate limiting is in-memory and per-instance** (`slowapi` default storage): warm lambda instances each keep their own counters, so the effective limit is "N/minute per instance", not global. This is a documented best-effort trade-off — it always works locally and under light traffic (demo/interview conditions), and it can never crash the app (the storage is a plain dict). A shared store (Redis/Upstash) is the upgrade path, deliberately cut ([IMPLEMENTATION_PLAN cut list](IMPLEMENTATION_PLAN.md)).
- **Region:** functions run in `sin1` (Singapore), matching Neon's `ap-southeast-1` — the DB hop is intra-region.
- **Env vars** live in the Vercel project settings and are injected into the function's environment at runtime; `vercel pull` in the deploy job makes them available during the build too. Nothing is baked into the artifact beyond what Next.js needs at build time (`BACKEND_URL`).

## 10. Secrets & variables inventory (quick reference)

GitHub **secrets**:

| GitHub secret | Used by | Purpose |
|---|---|---|
| `NEON_DATABASE_URL` | `deploy.yml → migrate` | Alembic against production DB (Neon **direct** endpoint) |
| `VERCEL_TOKEN` | `deploy.yml → deploy-api, deploy-web` | Vercel CLI auth |
| `VERCEL_ORG_ID` | `deploy.yml → deploy-api, deploy-web` | CLI scope (team) |
| `VERCEL_PROJECT_ID_API` | `deploy.yml → deploy-api` | CLI target project (deskflow-api) |
| `VERCEL_PROJECT_ID_WEB` | `deploy.yml → deploy-web` | CLI target project (deskflow-web) |
| `INTERNAL_TASK_TOKEN` | `scheduled.yml → sla-scan` | `X-Internal-Token` header for `/api/v1/internal/sla-scan`; **must equal the deskflow-api env var of the same name** |

GitHub **variables** (not secrets):

| GitHub variable | Used by | Purpose |
|---|---|---|
| `API_BASE_URL` | `scheduled.yml` (both jobs), `deploy.yml → deploy-web` (`BACKEND_URL`) | The deskflow-api production origin, e.g. `https://deskflow-api.vercel.app` |

Runtime configuration lives only in the Vercel projects (never in GitHub): deskflow-api — `DATABASE_URL` (Neon **pooled**), `SECRET_KEY`, `APP_ENV`, `INTERNAL_TASK_TOKEN`, thresholds, `LOG_LEVEL`; deskflow-web — `BACKEND_URL`, `NEXT_PUBLIC_APP_NAME`. How to create/rotate each: [AUTH_AND_SECURITY §9](AUTH_AND_SECURITY.md#9-secrets-handling).
