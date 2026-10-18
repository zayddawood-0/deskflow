# Deployment — DeskFlow

| Env | Frontend | API | Database |
|---|---|---|---|
| **Local** | `next dev` on :3000 (or Docker) | `uvicorn --reload` on :8000 (or Docker) | Postgres 16 in Docker Compose (`db`, port 5432) |
| **Production** | Vercel → `deskflow-web.vercel.app` | Render (free Web Service) → `deskflow-api.onrender.com` | Neon (free tier, Postgres 16) |

Same code in both; only env vars differ ([ENVIRONMENT](ENVIRONMENT.md)).

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

Dockerfiles: `backend/Dockerfile` (`python:3.12-slim`, `pip install -r requirements.txt`, `uvicorn app.main:app`), `frontend/Dockerfile` (node:20-alpine, `npm ci`, `npm run build`, `npm start`).

## 2. Neon (production database)

1. Create a free account → New project → region **AWS Singapore (ap-southeast-1)** (matches the Render region) → Postgres 16.
2. Copy the pooled connection string from the dashboard. Format expected by the app:
   `postgresql+psycopg2://USER:PASSWORD@HOST/deskflow?sslmode=require`
   (Neon's dashboard may give `postgres://` — both `session.py` and `alembic/env.py` normalize the scheme via `normalize_database_url`, but prefer setting the SQLAlchemy-ready form in the secret.)
3. Create the GitHub secret **`NEON_DATABASE_URL`** with that string (used by the CD migrate job only).
4. Add the Render public egress IPs / allow `0.0.0.0/0` for the free tier (Neon's default is anywherewith SSL — keep `sslmode=require`).
5. Branching: leave the default `main` branch; migrations always run against it. (Rollback uses `alembic downgrade`, §7.)

## 3. Render (API)

1. New → **Web Service** → connect the repo (or GitHub App) → root directory `backend`.
2. Settings:
   | Field | Value |
   |---|---|
   | Name | `deskflow-api` |
   | Runtime | Python |
   | Region | Singapore |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Health Check Path | `/api/v1/health` |
   | Instance Type | Free |
3. Environment (manual, not in repo):
   | Key | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `SECRET_KEY` | long random string (Generate button) |
   | `DATABASE_URL` | same Neon string as §2 |
   | `INTERNAL_TASK_TOKEN` | long random string — **must match the GitHub secret of the same name** (used by `scheduled.yml` → `X-Internal-Token`) |
   | `SLA_AT_RISK_THRESHOLD` | `0.75` |
   | `REOPEN_WINDOW_DAYS` | `7` |
   | `LOG_LEVEL` | `INFO` |
   | `CORS_ORIGINS` | *(leave empty — the browser talks to the API only through the Vercel rewrite proxy)* |
4. Copy the Render **Deploy Hook** URL (Service → Deploys → Deploy hooks → GitHub) into GitHub secret **`RENDER_DEPLOY_HOOK_URL`**. A `POST` to it triggers a fresh build+deploy — exactly what `deploy.yml` does after migrations succeed.

## 4. Vercel (frontend)

Deploys are **CI-only**: the committed `frontend/vercel.json` sets `"git": { "deploymentEnabled": false }`, which turns off Vercel's own Git integration so nothing ships except through `deploy.yml` (Vercel CLI). Do **not** connect the GitHub repo in the Vercel dashboard's Git settings.

1. `cd frontend && npx vercel link` locally (creates `.vercel/project.json`), then `npx vercel` for a first manual prod deploy if desired. `npx vercel link` may ask you to disable the Git integration — confirm; `vercel.json` already enforces it on every build.
2. Project → Settings → Environment Variables:
   | Key | Value |
   |---|---|
   | `BACKEND_URL` | `https://deskflow-api.onrender.com` (server-side rewrite destination; **no** trailing slash, no `/api/v1`) |
   | `NEXT_PUBLIC_APP_NAME` | `DeskFlow` |
   Set for Production + Preview + Development. The browser never calls the Render origin directly — `next.config.ts` rewrites `/api/:path*` → `${BACKEND_URL}/api/:path*` on the server.
3. GitHub secrets:
   | Secret | How to obtain |
   |---|---|
   | `VERCEL_TOKEN` | vercel.com → Account Settings → Tokens → Create (scope: full account or the project) |
   | `VERCEL_ORG_ID` | `.vercel/project.json` after `vercel link`, or Team Settings → General |
   | `VERCEL_PROJECT_ID` | same file / Project Settings → General |
4. Domain: the generated `*.vercel.app` domain is enough — no CORS wiring needed on Render (all browser traffic arrives same-origin through the rewrite proxy).

## 5. GitHub Actions workflows

### 5.1 `.github/workflows/ci.yml` (every push + PR)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    name: Backend (ruff + pytest)
    runs-on: ubuntu-24.04
    defaults:
      run:
        working-directory: backend
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: deskflow
          POSTGRES_PASSWORD: deskflow
          POSTGRES_DB: deskflow
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow
      TEST_DATABASE_URL: postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow_test
      SECRET_KEY: ci-only-secret-key-not-used-in-prod
      APP_ENV: development
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Create test database
        env:
          PGPASSWORD: deskflow
        run: |
          psql -h localhost -U deskflow -d deskflow -tAc \
            "SELECT 1 FROM pg_database WHERE datname='deskflow_test'" \
            | grep -q 1 || psql -h localhost -U deskflow -d deskflow \
            -c "CREATE DATABASE deskflow_test"
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest -q --cov=app --cov-report=term-missing

  frontend:
    name: Frontend (lint + types + build)
    runs-on: ubuntu-24.04
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run build
```

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

  deploy-backend:
    name: Render deploy hook
    needs: migrate
    runs-on: ubuntu-24.04
    steps:
      - name: Trigger Render deploy
        run: curl --fail --silent --show-error -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"

  deploy-frontend:
    name: Vercel production deploy
    needs: migrate
    runs-on: ubuntu-24.04
    defaults:
      run:
        working-directory: frontend
    env:
      VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
      VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
      VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
      BACKEND_URL: https://deskflow-api.onrender.com
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

Why `migrate` sets `SECRET_KEY`/`APP_ENV`: `alembic/env.py` calls `get_settings()` to read `DATABASE_URL`, and `Settings` requires `SECRET_KEY` — so the job must provide one (a throw-away literal is fine; the value is never used to sign anything during a migration) even though the DB URL is the only input that matters. `NEON_DATABASE_URL` is the sole secret this job needs; if it is unset, `DATABASE_URL` resolves to an empty string and Alembic fails immediately.

Ordering guarantees: **migrations before code** (Render's new image starts against an already-migrated DB; FastAPI is backward-compatible with the previous schema for one release because migrations are additive within a release). The frontend deploy is independent of the Render build duration.

> Branch-protection tip: require the CI workflow green before merging to `main` (repo Settings → Branches → `main` → Require status checks).

### 5.3 `.github/workflows/scheduled.yml` (cron every 15 min + manual)

Keeps the Render free instance awake (it sleeps after ~15 min idle) and runs the SLA scan so breaches are flagged and notified even when nobody has the app open. The scan is idempotent ([API_SPEC §12](API_SPEC.md#12-internal-apiv1internal)) — double runs never duplicate audit rows or notifications.

```yaml
name: Scheduled

on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch:

jobs:
  keep-warm:
    name: Ping API health (keep Render warm)
    runs-on: ubuntu-24.04
    steps:
      - name: GET /api/v1/health
        run: |
          curl --fail --silent --show-error --max-time 120 \
            "https://deskflow-api.onrender.com/api/v1/health"

  sla-scan:
    name: SLA breach / at-risk scan
    runs-on: ubuntu-24.04
    steps:
      - name: POST /api/v1/internal/sla-scan
        run: |
          curl --fail --silent --show-error --max-time 120 \
            -X POST \
            -H "X-Internal-Token: ${{ secrets.INTERNAL_TASK_TOKEN }}" \
            "https://deskflow-api.onrender.com/api/v1/internal/sla-scan"
```

Notes:
- `INTERNAL_TASK_TOKEN` (GitHub secret) must equal the Render env var of the same name — the backend compares the `X-Internal-Token` header against it with a constant-time compare.
- Until Phase 4 implements `POST /api/v1/internal/sla-scan`, the `sla-scan` job fails with a `404` (expected); `keep-warm` is already valid. The job goes green as soon as the endpoint ships.
- A red `keep-warm` run means the API was unreachable for 2 minutes (usually a cold start exceeding the timeout or an outage); a red `sla-scan` run means a bad/missing token or a server error — check the run's curl output.
- Cron on the free tier of GitHub Actions can be delayed by several minutes under load; 15-minute granularity is a best-effort wake-up, not a hard guarantee.
- Both jobs are plain `curl` — no checkout needed, they run in seconds.

## 6. Migration strategy

- **Source of truth:** `backend/alembic/versions/` — every schema change is a new revision, reviewed in the PR like any code.
- **Production runs:** only through the `migrate` job in `deploy.yml` (`alembic upgrade head` from GitHub Actions with `NEON_DATABASE_URL`). Render never runs migrations at boot (no race with the web process, no migration logs mixed into app logs).
- **Rules:**
  1. Additive-first: add columns/tables as nullable or with defaults — the previous app version must keep working during the deploy window.
  2. Never edit an applied revision; fix forward.
  3. Destructive changes (drop/rename) ship in two releases: (a) stop using the old thing + add the new thing, (b) drop later.
  4. The initial migration `0001_initial` also seeds `sla_policies` + the `('ticket', 1040)` counter row idempotently, so a fresh Neon DB matches local.
- **Prod DB bootstrap:** empty Neon DB → first `deploy.yml` run creates the whole schema; then run the seed once manually if demo data is wanted in prod:
  `gh workflow run deploy.yml` is not enough — run locally `DATABASE_URL=<neon> python -m app.db.seed` (or a one-off Render shell).

## 7. Rollback notes

| Failure | Fix |
|---|---|
| Bad migration detected immediately after merge | `cd backend && DATABASE_URL=$NEON_DATABASE_URL alembic downgrade -1` from a workstation, then ship a fix-forward revision; Render keeps running the previous image until the next deploy |
| Bad API build (crash loop) | Render → Deploys → roll back to the previous successful deploy (one click); no DB change needed for pure-code regressions |
| Bad frontend build | Vercel → Deployments → promote the previous deployment (instant rollback, no build) |
| Both | revert commit on `main` and push; CI/CD redoes the pipeline in the right order |
| `SECRET_KEY` rotated accidentally | all access tokens invalidate; users re-login (refresh tokens keep working only if their hash lookup still passes — they do; only JWTs die). Communicate as a forced re-login |

Free-tier caveat: Render free services are deleted after 90 days of inactivity — the `scheduled.yml` cron ping on `/api/v1/health` every 15 min keeps the instance alive (and awake, mostly) so the service is never idle enough to be deleted.

## 8. Post-deploy smoke test

Run after every production deploy (also the manual UI regression checklist):

1. `curl https://deskflow-api.onrender.com/api/v1/health` → `{"status":"ok","database":"up","version":"1.0.0"}` (first call may take 30–60 s cold).
2. Login as `agent1@deskflow.dev` → dashboard loads, KPI numbers present, charts render.
3. Login as `requester1@deskflow.dev` → `/tickets` lists only own tickets; create a ticket with a `CRITICAL` priority → due dates visible, countdown ticking.
4. Login as agent → new ticket appears (auto-assigned), self-assign a second one, add an internal note, put a third on hold → "Paused" state shown.
5. Transition one to `RESOLVED`; try an invalid transition (`PATCH`-less quick check via Swagger: `OPEN→CLOSED` on some ticket) → 409 with code.
6. Requester reopens the resolved ticket; admin sees both events in `/audit` filtered by that ticket.
7. Bell shows unread items; mark-all-read works.
8. `/admin/sla` save works (revert the change after checking).
9. Console free of errors; mobile width spot-check; Network tab shows all API calls going to the same origin (`/api/v1/*`, i.e. the Vercel domain — never direct to Render).

## 9. Render free-tier cold starts (and how the frontend handles them)

- After ~15 min without traffic, Render puts the free service to sleep. The first request takes **30–60 s** while the container and DB pool boot; `/api/v1/health` is the wake-up call (also hit by `scheduled.yml` every 15 min, so the instance rarely sleeps while the cron is green).
- Frontend mitigations (implemented in `lib/api-client.ts` + dashboard page):
  - 15 s request timeout (AbortController) → on timeout the UI shows a **"Waking up the server…"** skeleton with an automatic retry after 5 s (one retry, then a friendly error Card with a manual Retry button).
  - All list/detail pages use skeletons (no blank flash).
  - The dashboard's parallel queries fail soft per-widget (one failed panel doesn't kill the page).
- Accept this as a free-tier reality in the README demo note (already documented).

## 10. Secrets inventory (quick reference)

| GitHub secret | Used by | Purpose |
|---|---|---|
| `NEON_DATABASE_URL` | `deploy.yml → migrate` | Alembic against production DB |
| `RENDER_DEPLOY_HOOK_URL` | `deploy.yml → deploy-backend` | Triggers Render rebuild |
| `INTERNAL_TASK_TOKEN` | `scheduled.yml → sla-scan` | `X-Internal-Token` header for `/api/v1/internal/sla-scan`; **must equal the Render env var of the same name** |
| `VERCEL_TOKEN` | `deploy.yml → deploy-frontend` | Vercel CLI auth |
| `VERCEL_ORG_ID` | `deploy.yml → deploy-frontend` | CLI scope |
| `VERCEL_PROJECT_ID` | `deploy.yml → deploy-frontend` | CLI target project |

Runtime secrets live only in Render's env panel (never in GitHub): `SECRET_KEY`, `DATABASE_URL`, `INTERNAL_TASK_TOKEN` (the shared one — also a GitHub secret), thresholds, `LOG_LEVEL`. How to create/rotate each: [AUTH_AND_SECURITY §9](AUTH_AND_SECURITY.md#9-secrets-handling).
