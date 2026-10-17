# Environment variables — DeskFlow

Two env files, both git-ignored; the committed templates are `backend/.env.example` and `frontend/.env.example`.

## 1. Backend (`backend/.env`)

| Name | Purpose | Required | Local example | Production value |
|---|---|---|---|---|
| `APP_ENV` | `development` \| `production` (gates fail-fast startup checks, e.g. requiring a strong `SECRET_KEY`) | no (default `development`) | `development` | `production` |
| `SECRET_KEY` | HS256 signing key for access tokens (≥ 32 random chars) | **yes** | `local-dev-secret-change-me-0123456789abcdef` | random 64-char string (Render env) |
| `ALGORITHM` | JWT algorithm | no (`HS256`) | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes | no (`30`) | `30` | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime in days | no (`14`) | `14` | `14` |
| `DATABASE_URL` | SQLAlchemy URL `postgresql+psycopg2://user:pass@host:port/db` (+`?sslmode=require` remote) | **yes** | `postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow` | Neon URL (normalized; `postgres://` accepted) |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | no (`http://localhost:3000`) | `http://localhost:3000` | `https://deskflow-web.vercel.app` |
| `SLA_AT_RISK_THRESHOLD` | Fraction of an SLA target that means `AT_RISK` | no (`0.75`) | `0.75` | `0.75` |
| `REOPEN_WINDOW_DAYS` | Days after `CLOSED` during which `CLOSED→REOPENED` is allowed | no (`7`) | `7` | `7` |
| `SLA_SCAN_SECRET` | Shared secret required by `POST /api/v1/internal/sla-scan` (`X-SLA-Scan-Secret`) | no (default local literal) | `local-scan-secret` | random string |
| `LOG_LEVEL` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` | no (`INFO`) | `DEBUG` | `INFO` |
| `APP_VERSION` | Reported by `/health` (optional override of the baked default `1.0.0`) | no | `1.0.0` | `1.0.0` |

Notes:
- `session.py` normalizes `DATABASE_URL`: `postgres://` → `postgresql+psycopg2://`, and adds `sslmode=require` when the host is not `localhost` (covers Neon + Render).
- Startup fails fast when `APP_ENV=production` and `SECRET_KEY` is missing or < 32 chars.
- CI supplies `DATABASE_URL` (service container) and `SECRET_KEY` inline — no `.env` file in CI.

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
SLA_SCAN_SECRET=local-scan-secret
LOG_LEVEL=DEBUG
```

## 2. Frontend (`frontend/.env.local`)

| Name | Purpose | Required | Local example | Production value |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the API **including** the `/api/v1` prefix | **yes** | `http://localhost:8000/api/v1` | `https://deskflow-api.onrender.com/api/v1` |
| `NEXT_PUBLIC_APP_NAME` | Display name in the navbar/toasts | no (`DeskFlow`) | `DeskFlow` | `DeskFlow` |

Rules:
- Only `NEXT_PUBLIC_*` vars reach the browser bundle — never put tokens or secrets there.
- Set in Vercel → Project → Settings → Environment Variables (Production/Preview/Development all need a value; Preview can point at the same Render API).

### `frontend/.env.example` (committed template; copy to `.env.local`)

```dotenv
# DeskFlow frontend — copy to .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=DeskFlow
```

## 3. Where each variable lives

| Context | Backend vars | Frontend vars |
|---|---|---|
| Local dev | `backend/.env` (from `.env.example`) | `frontend/.env.local` (from `.env.example`) |
| Local Docker Compose | inline in `docker-compose.yml` `environment:` | inline `NEXT_PUBLIC_API_URL` |
| CI (`ci.yml`) | inline job `env:` (test DB + dummy secret) | inline `NEXT_PUBLIC_API_URL` (prod URL — build-time only) |
| Production | Render → Environment panel (`APP_ENV`, `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `SLA_SCAN_SECRET`, `LOG_LEVEL`, thresholds) | Vercel → Project env vars (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_NAME`) |
| CD pipeline | GitHub Actions secrets (`NEON_DATABASE_URL`, `RENDER_DEPLOY_HOOK_URL`, `VERCEL_*`) — pipeline-only, never app runtime | same |

Setup steps for the production services: [DEPLOYMENT §2–§4](DEPLOYMENT.md#2-neon-production-database).
