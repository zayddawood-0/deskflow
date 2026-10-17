# Auth & Security — DeskFlow

| | |
|---|---|
| Related | [API_SPEC §4](API_SPEC.md#4-auth-apiv1auth) · [ARCHITECTURE §5](ARCHITECTURE.md#5-cross-cutting-concerns) · [ENVIRONMENT](ENVIRONMENT.md) |

## 1. Token model

| | Access token | Refresh token |
|---|---|---|
| Type | JWT (`PyJWT`), HS256 | Opaque random string (`rt_<43 url-safe chars>`), stored **hashed** (SHA-256) in `refresh_tokens` |
| Lifetime | `ACCESS_TOKEN_EXPIRE_MINUTES = 30` | `REFRESH_TOKEN_EXPIRE_DAYS = 14` |
| Claims / storage | `sub` (user id), `role`, `iat`, `exp`, `jti` | `token_hash`, `user_id`, `expires_at`, `revoked_at`, `user_agent`, no IP storage |
| Sent | `Authorization: Bearer <jwt>` on every request | only in `/auth/refresh` and `/auth/logout` bodies |
| Revocation | stateless (expires naturally) | DB-backed: rotated on refresh, revoked on logout, password change, deactivation |
| Signed with | `SECRET_KEY` (≥32 chars) + `ALGORITHM = HS256` | n/a (lookup by hash) |

Password hashing: **argon2id** via `argon2-cffi` (`PasswordHasher`, default params; verification is constant-time and hash-format aware).

## 2. Login → refresh sequence

```mermaid
sequenceDiagram
    autonumber
    participant F as Frontend (AuthProvider + api-client.ts)
    participant A as FastAPI /auth
    participant DB as PostgreSQL

    F->>A: POST /auth/login {email, password}
    Note over A: slowapi: max 5 req/min/IP
    A->>DB: SELECT user by email
    A->>A: argon2 verify (fake-hash on missing user → constant time)
    alt valid + is_active
        A->>DB: INSERT refresh_tokens (hash, expires_at)
        A-->>F: 200 {access_token, refresh_token, expires_in, user}
        F->>F: access in memory, refresh in localStorage
    else invalid
        A-->>F: 401 {error: UNAUTHORIZED, "Invalid email or password."}
    end

    Note over F: later — API call with expired JWT
    F->>A: GET /tickets (expired access token)
    A-->>F: 401 UNAUTHORIZED
    F->>A: POST /auth/refresh {refresh_token}
    A->>DB: SELECT refresh_tokens WHERE token_hash = sha256(rt) AND revoked_at IS NULL AND expires_at > now
    A->>DB: UPDATE old row revoked_at = now(); INSERT new refresh row
    A-->>F: 200 {access_token, refresh_token, ...} (new pair)
    F->>A: retry original GET /tickets with new Bearer
    A-->>F: 200 {items, ...}
```

Failure paths: refresh token missing/unknown/expired/revoked → `401 UNAUTHORIZED`; the client clears both tokens and redirects to `/login`. The retry-once logic lives **only** in `src/lib/api-client.ts` (single-flight: concurrent 401s share one refresh promise).

## 3. Token storage (frontend)

| Token | Where | Why |
|---|---|---|
| Access token (30 min) | **In memory** — React `AuthProvider` context (module-level ref for non-React callers) | Not persisted → survives reload only via refresh; XSS cannot read `localStorage` for it after reload without re-refreshing; simple. |
| Refresh token (14 days) | **`localStorage["deskflow_refresh"]`** | Cross-site deployment (Vercel frontend ↔ Render API) makes `httpOnly; SameSite=Cookie` flows a config/CSRF project of their own on free tiers. |

Accepted tradeoff (documented deliberately): an XSS that runs our JS could read the refresh token. Mitigations: no `dangerouslySetInnerHTML` anywhere, no user-supplied HTML rendering (comments are plain text, React escapes by default), strict dependency hygiene, refresh token rotation limits reuse (a stolen token works at most once after the legit client also refreshes — rotation marks the old one revoked), and logout/password-change revoke tokens. **If time remains:** move to a `httpOnly` `__Host-` cookie by proxying `/auth/*` through Next.js route handlers.

localStorage key: `deskflow_refresh`. Access token is never written to storage.

## 4. RBAC permission matrix

Rows = action, columns = role. `✓` allowed, `✗` denied, `own` = only tickets where `requester_id = caller`.

| Action | requester | agent | admin |
|---|---|---|---|
| Register / login / refresh / logout | ✓ | ✓ | ✓ |
| View own profile, change own password | ✓ | ✓ | ✓ |
| Create ticket | ✓ | ✓ | ✓ |
| List tickets | own only | all | all |
| View ticket detail / timeline | own only | all | all |
| Edit title/description | own, status ∈ {OPEN, REOPENED} | all | all |
| Edit priority / category | ✗ | ✓ | ✓ |
| Add public comment | own tickets | all | all |
| Add internal note (`is_public=false`) | ✗ | ✓ | ✓ |
| Transition status | T6/T7/T8 on own tickets | T1–T9 | T1–T9 |
| Self-assign | ✗ | ✓ (unassigned only) | ✓ |
| Assign to someone else / unassign | ✗ | ✗ | ✓ |
| List users / create user | ✗ | ✗ | ✓ |
| Change user role / active flag | ✗ | ✗ | ✓ (not self-demotion) |
| Deactivate user | ✗ | ✗ | ✓ (not self) |
| List categories | ✓ | ✓ | ✓ |
| Create/update/deactivate category | ✗ | ✗ | ✓ |
| View SLA policies | ✓ | ✓ | ✓ |
| Update SLA policies | ✗ | ✗ | ✓ |
| View global audit log | ✗ | ✗ | ✓ |
| View dashboard endpoints | ✗ | ✓ | ✓ |
| View notifications | own | own | own |
| `POST /internal/sla-scan` | ✗ (requires `X-SLA-Scan-Secret`) | same | same |

Enforcement points:
1. **Backend (authoritative):** `get_current_user` dependency (JWT → user, 401 if invalid/inactive) + `require_role("admin")` / ownership checks in routers/services; transitions additionally validated by the state machine (409/403).
2. **Frontend (UX only):** `middleware.ts` redirects unauthenticated users to `/login` and wrong-role users away from `/admin/*`, `/audit`, `/dashboard`; `RoleGuard` components hide controls (buttons, tabs) the role cannot use. Never rely on this for security.

## 5. Password policy

- Minimum **8** characters, must contain at least one uppercase letter, one lowercase letter and one digit (enforced by the same Zod schema on the frontend and a Pydantic `field_validator` on the backend).
- Max length 128 (argon2 input guard).
- Stored as argon2id; **never** logged, never returned by any endpoint, never included in audit `old/new_value`.
- Login failure message is always generic: "Invalid email or password." (no user enumeration).
- Password change (`POST /auth/change-password`) requires the current password and revokes all other refresh tokens.

## 6. Input validation

- **Pydantic v2** request models on every endpoint (`422 VALIDATION_ERROR` + per-field `details` from the global `RequestValidationError` handler).
- Enums validated against the native Postgres enums via Python `Enum` classes; unknown value → 422 (not 500).
- UUIDs parsed by type → invalid uuid → 422, not a DB error.
- Length/regex checks mirror the DB constraints (title 5–200, description ≥ 10, comment body 1–5000, name ≤ 80…).
- **SQL injection:** only parameterized SQLAlchemy statements; no raw string-built SQL; search uses `ILIKE` with bound parameters.
- Authorization is applied **before** heavy work: ticket visibility filter is part of the repository query, so foreign ids return 404.

## 7. CORS configuration

```python
# app/core/config.py — built from settings.cors_origins (comma-separated env var)
allow_origins=settings.cors_origins_list   # prod: https://deskflow-web.vercel.app
allow_credentials=False                     # Bearer tokens, not cookies
allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
allow_headers=["Authorization", "Content-Type"]
max_age=600
```

- Local: `CORS_ORIGINS=http://localhost:3000`. Prod: exactly the Vercel domain — never `*`.
- Because credentials are off, CSRF is not applicable to the API (tokens travel in headers, not cookies).

## 8. Rate limiting

- `slowapi` (`limits` storage: in-memory per process; documented as non-shared across instances — Render runs a single free instance, so it is exact).
- `POST /auth/login`: **5 requests/minute per client IP** → `429 RATE_LIMITED` with `Retry-After`.
- `POST /auth/register`: 10/minute per IP.
- All other endpoints: unlimited in MVP (per-instance reality: free tier; stretch = global limiter).
- The frontend surfaces 429 as "Too many attempts — try again in a minute." and disables the submit button for the retry window.

## 9. Secrets handling

| Secret | Local | Prod | Notes |
|---|---|---|---|
| `SECRET_KEY` | generated into `backend/.env` (never committed) | GitHub secret → Render env var | ≥ 32 random chars; rotating it invalidates all access tokens |
| `DATABASE_URL` | docker-compose defaults in `.env.example` | Neon connection string (GitHub `NEON_DATABASE_URL` + Render env) | `postgresql+psycopg2://user:pass@host/db?sslmode=require` |
| `SLA_SCAN_SECRET` | literal in `.env.example` | GitHub secret → Render env var | protects `/internal/sla-scan` |
| `VERCEL_TOKEN` / `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID` | n/a | GitHub secrets only | CI/CD only, never in app runtime |
| `RENDER_DEPLOY_HOOK_URL` | n/a | GitHub secret only | contains an unguessable hook id — treat as secret |

Rules: `.env` and `.env.local` are git-ignored; only `backend/.env.example` and `frontend/.env.example` are committed; no secret appears in code, logs, audit rows, or the frontend bundle (`NEXT_PUBLIC_` vars are public by definition — never put tokens there).

## 10. OWASP top 10 (app-relevant checklist)

| # | Risk | Mitigation in DeskFlow | Where |
|---|---|---|---|
| A01 | Broken access control | Server-side role + ownership checks on every endpoint; visibility baked into repository queries (404 for foreign tickets); admin-only routers behind `require_role`; state machine rejects illegal moves | `app/core/deps.py`, routers, `ticket_service.transition` |
| A02 | Cryptographic failures | argon2id password hashing; HS256 JWT with strong `SECRET_KEY`; refresh tokens stored hashed (SHA-256); TLS everywhere (Vercel/Render/Neon force HTTPS); no plaintext secrets in repo | `app/core/security.py` |
| A03 | Injection | Parameterized SQLAlchemy only; no `text()` with interpolation; enums validated in Pydantic; React auto-escapes rendered text | repositories, schemas |
| A04 | Insecure design | Layered architecture with one-way dependencies; audit log immutable (DB trigger); append-only audit = tamper evidence | [ARCHITECTURE §3](ARCHITECTURE.md#3-backend-layering) |
| A05 | Security misconfiguration | CORS pinned to one origin; `allow_credentials=False`; Swagger enabled only when `APP_ENV != production` (docstrings say: disable in prod via setting); no default secrets (startup fails if `SECRET_KEY` is empty in prod) | `app/core/config.py` |
| A06 | Vulnerable components | Small, mainstream dependency set; `pip`/`npm` lockfiles committed; Dependabot optional | `requirements.txt`, `package-lock.json` |
| A07 | Identification & auth failures | JWT + rotation, rate-limited login, generic failure messages, inactive users rejected at login **and** at token verification, password policy | §1–§5, §8 |
| A08 | Data & integrity failures | Pydantic validation both sides; DB constraints (NOT NULL, UNIQUE, FK) as second line; single-transaction mutations (change + audit commit together) | schema, services |
| A09 | Logging & monitoring failures | Structured request logs with `request_id`/`user_id` (tokens and passwords never logged); `GET /health` for uptime checks | `app/core/logging.py` |
| A10 | SSRF | None — the app makes no outbound requests at all in MVP | — |

Explicit non-claims (honest scope): no CSRF tokens (not needed without cookies), no WAF/bot protection, in-memory rate limiting, refresh token in localStorage (§3).
