# Auth & Security — DeskFlow

| | |
|---|---|
| Related | [API_SPEC §4](API_SPEC.md#4-auth-apiv1auth) · [ARCHITECTURE §5](ARCHITECTURE.md#5-cross-cutting-concerns) · [ENVIRONMENT](ENVIRONMENT.md) |

## 1. Token model

| | Access token | Refresh token |
|---|---|---|
| Type | JWT (`PyJWT`), HS256 | Opaque random string (`rt_<43 url-safe chars>`), stored **hashed** (SHA-256) in `refresh_tokens` |
| Lifetime | `ACCESS_TOKEN_EXPIRE_MINUTES = 30` | `REFRESH_TOKEN_EXPIRE_DAYS = 14` |
| Transport | `Authorization: Bearer <jwt>` header, set by the JS client from memory | **httpOnly cookie** set by the backend (`Set-Cookie` on login/refresh): `HttpOnly; SameSite=Lax; Path=/api/v1/auth; Secure` in production; cleared on logout |
| Claims / storage | `sub` (user id), `role`, `iat`, `exp`, `jti` | `token_hash`, `user_id`, `expires_at`, `revoked_at`, `created_at` (no IP/UA storage) |
| Revocation | stateless (expires naturally) | DB-backed: rotated on refresh, revoked on logout, password change, deactivation |
| Signed with | `SECRET_KEY` (≥32 chars) + `ALGORITHM = HS256` | n/a (lookup by hash) |

Password hashing: **argon2id** via `argon2-cffi` (`PasswordHasher`, default params; verification is constant-time and hash-format aware).

## 2. Login → refresh sequence

All frontend calls are **same-origin**: the browser talks to `https://<vercel-domain>/api/v1/...` and Next.js `rewrites()` in `next.config.ts` proxies to `${BACKEND_URL}/api/v1/...` on Render. The cookie is therefore always sent automatically on `/api/v1/auth/*` requests — JS never reads or writes it.

```mermaid
sequenceDiagram
    autonumber
    participant F as Frontend (AuthProvider + api-client.ts)
    participant N as Next.js rewrite proxy (/api/*)
    participant A as FastAPI /api/v1/auth
    participant DB as PostgreSQL

    F->>N: POST /api/v1/auth/login {email, password}
    N->>A: proxied (adds nothing; same request)
    Note over A: slowapi: max 5 req/min/IP
    A->>DB: SELECT user by email
    A->>A: argon2 verify (fake-hash on missing user → constant time)
    alt valid + is_active
        A->>DB: INSERT refresh_tokens (hash, expires_at)
        A-->>N: 200 {access_token, expires_in, user}<br/>Set-Cookie: rt=...; HttpOnly; SameSite=Lax; Path=/api/v1/auth
        N-->>F: same response + cookie stored by the browser
        F->>F: access token in memory (cookie invisible to JS)
    else invalid
        A-->>F: 401 {error: UNAUTHORIZED, "Invalid email or password."}
    end

    Note over F: later — API call with expired JWT
    F->>N: GET /api/v1/tickets (expired Bearer)
    N->>A: proxied
    A-->>F: 401 UNAUTHORIZED
    F->>N: POST /api/v1/auth/refresh   (browser attaches the httpOnly cookie — Path matches)
    N->>A: proxied
    A->>DB: SELECT refresh_tokens WHERE token_hash = sha256(cookie rt) AND revoked_at IS NULL AND expires_at > now
    A->>DB: UPDATE old row revoked_at = now(); INSERT new refresh row
    A-->>F: 200 {access_token, expires_in, user} + Set-Cookie (rotated rt)
    F->>N: retry original GET /api/v1/tickets with new Bearer
    A-->>F: 200 {items, ...}
```

Failure paths: refresh cookie missing/unknown/expired/revoked → `401 UNAUTHORIZED`; the client clears its in-memory token and redirects to `/login`. The retry-once logic lives **only** in `src/lib/api-client.ts` (single-flight: concurrent 401s share one refresh promise). Because the cookie is scoped to `Path=/api/v1/auth`, it is **never sent** with any other request — including page navigations, which is why route gating is client-side (§3).

## 3. Token storage (frontend)

| Token | Where | Why |
|---|---|---|
| Access token (30 min) | **In memory** — React `AuthProvider` context (module-level ref for non-React callers) | Never persisted to `localStorage`/`sessionStorage`; a reload silently re-hydrates via one cookie refresh call. |
| Refresh token (14 days) | **httpOnly cookie** set by FastAPI (`Path=/api/v1/auth; SameSite=Lax`, `Secure` in prod) | Invisible to JavaScript (XSS cannot exfiltrate it); sent automatically by the browser only to the auth endpoints. |

Consequences of the `Path=/api/v1/auth` scope:
- Page requests (`/dashboard`, etc.) do not carry the cookie, so `middleware.ts` **cannot** be used for auth gating — route protection is entirely client-side: `AuthProvider` performs one `POST /api/v1/auth/refresh` on mount; while it resolves, protected pages show a skeleton; on failure the user is redirected to `/login`. `RoleGuard` handles role-based redirects once `user` is known. The backend remains the only real security boundary.
- Logout: `POST /api/v1/auth/logout` revokes the token server-side **and** returns `Set-Cookie` with an empty value + expired date (`Clear-Cookie` semantics).
- Password change / deactivation revoke all refresh tokens server-side, so the cookie becomes a dead letter on its next use.

CSRF posture: the cookie is `SameSite=Lax`, so browsers do not attach it to cross-site `POST/PUT/PATCH/DELETE` subrequests; every endpoint consumes/produces JSON (no form-encoded state changes); the cookie is only accepted on `/api/v1/auth/*` paths. This is sufficient for the MVP threat model without CSRF tokens.

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
| `POST /internal/sla-scan` | ✗ (requires `X-Internal-Token` == `INTERNAL_TASK_TOKEN`) | same | same |

Enforcement points:
1. **Backend (authoritative):** `get_current_user` dependency (JWT → user, 401 if invalid/inactive) + `require_role("admin")` / ownership checks in routers/services; transitions additionally validated by the state machine (409/403).
2. **Frontend (UX only):** client-side gating — `AuthProvider` bootstraps the session via one silent `POST /api/v1/auth/refresh` on mount (httpOnly cookie), then `RoleGuard` components redirect wrong roles and hide controls (buttons, tabs) the role cannot use. Never rely on this for security.

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

The browser **never talks to the Render API cross-origin**: the frontend calls same-origin `/api/v1/*` and Next.js `rewrites()` (server-side) proxies to `BACKEND_URL`. The refresh cookie is same-site by construction, and no CORS headers are required for the app itself.

CORS is still configured on the API for two secondary consumers:

```python
# app/core/config.py — built from settings.cors_origins (comma-separated env var)
allow_origins=settings.cors_origins_list   # local: http://localhost:3000 (direct cross-port testing)
allow_credentials=False                     # the refresh cookie is path-scoped + proxied; never sent cross-origin
allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
allow_headers=["Authorization", "Content-Type"]
max_age=600
```

- Local dev: `CORS_ORIGINS=http://localhost:3000` allows poking the API directly (Swagger experiments, curl from a browser extension) while the app itself still goes through the Next rewrite (`BACKEND_URL=http://localhost:8000`).
- Production: leave `CORS_ORIGINS` empty or set to nothing meaningful — no browser origin needs it (Swagger UI on Render is served same-origin with the API). Never `*`.

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
| `INTERNAL_TASK_TOKEN` | local literal in `.env.example` | GitHub secret **and** Render env var (**must be the identical value**) | protects `/internal/sla-scan` via the `X-Internal-Token` header |
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
| A05 | Security misconfiguration | CORS conservative and app-irrelevant (proxy; `allow_credentials=False`); Swagger UI **kept on in prod on purpose** (part of the demo; all endpoints still require auth) — see DEPLOYMENT; no default secrets (startup fails if `SECRET_KEY` is empty/short in prod); secure cookie flags in prod (`Secure`) | `app/core/config.py` |
| A06 | Vulnerable components | Small, mainstream dependency set; `pip`/`npm` lockfiles committed; Dependabot optional | `requirements.txt`, `package-lock.json` |
| A07 | Identification & auth failures | JWT + rotation, rate-limited login, generic failure messages, inactive users rejected at login **and** at token verification, password policy | §1–§5, §8 |
| A08 | Data & integrity failures | Pydantic validation both sides; DB constraints (NOT NULL, UNIQUE, FK) as second line; single-transaction mutations (change + audit commit together) | schema, services |
| A09 | Logging & monitoring failures | Structured request logs with `request_id`/`user_id` (tokens and passwords never logged); `GET /api/v1/health` for uptime checks; `scheduled.yml` pings health every 15 min to keep Render warm and runs the SLA scan | `app/core/logging.py` |
| A10 | SSRF | None — the app makes no outbound requests at all in MVP | — |

Explicit non-claims (honest scope): no CSRF tokens (the refresh cookie is `SameSite=Lax` + path-scoped + JSON-only endpoints — see §3), no WAF/bot protection, in-memory rate limiting (single Render instance), access token lives only in JS memory with a silent cookie refresh on boot.
