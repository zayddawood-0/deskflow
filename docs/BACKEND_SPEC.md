# Backend Spec — DeskFlow

| | |
|---|---|
| Stack | Python 3.12 · FastAPI · SQLAlchemy 2.0 (**sync**, psycopg2) · Pydantic v2 · Alembic · PyJWT · argon2-cffi · slowapi |
| Layering | routers → services → repositories → models ([ARCHITECTURE §3](ARCHITECTURE.md#3-backend-layering)) |

## 1. Folder structure

```
backend/
├── requirements.txt                # runtime deps (pinned)
├── requirements-dev.txt            # pytest, httpx, ruff, coverage, pytest-cov
├── alembic.ini
├── Dockerfile                      # python:3.12-slim, uvicorn app.main:app
├── .env.example
├── alembic/
│   ├── env.py                      # imports app.db.base.Base + app.models.* (target_metadata)
│   └── versions/
│       └── 0001_initial.py         # ALL enums, tables, indexes, trigger, seed rows
├── app/
│   ├── main.py                     # create_app(): CORS, routers, exception handlers, /api/v1/health, logging
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # api_router = APIRouter(prefix="/api/v1"); includes all resource routers
│   │       └── routers/
│   │           ├── auth.py
│   │           ├── users.py
│   │           ├── categories.py
│   │           ├── sla_policies.py
│   │           ├── tickets.py      # also mounts /status /assign /self-assign /unassign /comments /audit subpaths
│   │           ├── audit.py
│   │           ├── dashboard.py
│   │           ├── notifications.py
│   │           └── internal.py     # POST /internal/sla-scan
│   ├── core/
│   │   ├── config.py               # Settings (pydantic-settings), get_settings() cached
│   │   ├── security.py             # argon2 hash/verify, create_access_token, decode_token, new_refresh_token, hash_token
│   │   ├── deps.py                 # get_db, get_current_user, require_roles(...), get_request_ip
│   │   ├── errors.py               # AppError hierarchy + register_exception_handlers()
│   │   ├── rate_limit.py           # slowapi Limiter(get_remote_address), login/register limits
│   │   └── logging.py              # configure_logging(): JSON logs, request_id middleware
│   ├── db/
│   │   ├── base.py                 # Base(DeclarativeBase)
│   │   ├── session.py              # engine (pool_pre_ping), SessionLocal, get_db()
│   │   └── seed.py                 # python -m app.db.seed  (idempotent)
│   ├── models/                     # SQLAlchemy 2.0 Mapped classes (mirror DATABASE_SCHEMA)
│   │   ├── enums.py                # UserRole, TicketStatus, TicketPriority, NotificationType, SLAState(str, Enum)
│   │   ├── user.py  category.py  sla_policy.py  ticket.py
│   │   ├── ticket_comment.py  audit_log.py  notification.py
│   │   ├── refresh_token.py  counter.py
│   ├── schemas/                    # Pydantic v2 request/response models
│   │   ├── common.py               # Page[T], ErrorEnvelope, Message
│   │   ├── auth.py  user.py  category.py  sla_policy.py
│   │   ├── ticket.py  comment.py  audit.py  dashboard.py  notification.py
│   ├── services/
│   │   ├── auth_service.py         # register, login (sets refresh cookie), refresh (rotation, rotates cookie), logout (clears cookie), change_password
│   │   ├── user_service.py
│   │   ├── category_service.py
│   │   ├── sla_policy_service.py
│   │   ├── ticket_service.py       # create, list, get, update  → delegates transitions/assignment
│   │   ├── status_machine.py       # TRANSITIONS table + validate_transition()
│   │   ├── sla_service.py          # compute_due_dates, sla_state(), check_and_persist_breaches()
│   │   ├── assignment_service.py   # pick_least_loaded_agent(), assign(), self_assign(), unassign()
│   │   ├── comment_service.py      # create/list with visibility rules, first-response side effects
│   │   ├── audit_service.py        # record(db, actor, action, ...) — used by ALL services
│   │   ├── notification_service.py # notify(user, type, title, body, ticket) with dedup + active check
│   │   └── dashboard_service.py    # stats, tickets_per_day, sla_trend, breakdown, recent
│   └── repositories/
│       ├── user_repository.py
│       ├── category_repository.py
│       ├── sla_policy_repository.py
│       ├── ticket_repository.py    # list query builder with filters/visibility, ticket number allocation
│       ├── comment_repository.py
│       ├── audit_repository.py
│       ├── notification_repository.py
│       └── refresh_token_repository.py
└── tests/
    ├── conftest.py                 # engine → test DB, per-test transaction rollback fixture, TestClient, factories
    ├── factories.py                # make_user / make_ticket / make_comment helpers
    ├── test_health.py
    ├── test_auth.py
    ├── test_rbac.py
    ├── test_tickets.py
    ├── test_transitions.py
    ├── test_sla.py
    ├── test_assignment.py
    ├── test_comments.py
    ├── test_audit.py
    ├── test_dashboard.py
    ├── test_notifications.py
    └── test_categories_and_sla.py
```

## 2. Configuration (`app/core/config.py`)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"                 # APP_ENV
    secret_key: str                              # SECRET_KEY (required)
    algorithm: str = "HS256"                     # ALGORITHM
    access_token_expire_minutes: int = 30        # ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = 14          # REFRESH_TOKEN_EXPIRE_DAYS
    database_url: str                            # DATABASE_URL
    cors_origins: str = "http://localhost:3000"  # CORS_ORIGINS (comma-separated)
    sla_at_risk_threshold: float = 0.75          # SLA_AT_RISK_THRESHOLD
    reopen_window_days: int = 7                  # REOPEN_WINDOW_DAYS
    internal_task_token: str = "local-internal-token"  # INTERNAL_TASK_TOKEN (X-Internal-Token for /internal/sla-scan)
    log_level: str = "INFO"                      # LOG_LEVEL
    app_version: str = "1.0.0"

    @property
    def cors_origins_list(self) -> list[str]: ...

@lru_cache
def get_settings() -> Settings: ...
```

- Startup guard: if `app_env == "production"` and `secret_key` is empty/short (<32 chars) → fail fast.
- `DATABASE_URL` normalization in `session.py`: pure function that replaces `postgres://`/`postgresql://` → `postgresql+psycopg2://`, ensures `sslmode=require` when the host is not `localhost` (Neon friendly), strips surrounding whitespace, and raises a clear `DATABASE_URL is required and must not be empty` error for an empty value. On Vercel (`VERCEL=1`) the engine uses `NullPool` (serverless).

## 3. Dependency injection (`app/core/deps.py`)

| Dependency | Behavior |
|---|---|
| `get_db()` | yields a `Session` from `SessionLocal`; commits on clean exit, rolls back on exception; always closes |
| `get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db = Depends(get_db))` | decode JWT → `sub` → load user → `401 UNAUTHORIZED` if missing/expired/invalid/inactive |
| `require_roles(*roles)` | factory returning a dependency: `get_current_user` + role check → `403 FORBIDDEN` (`Depends(require_roles("admin"))`) |
| `get_internal_token_header(x_internal_token: str = Header(...))` | constant-time compare with `settings.internal_task_token` → else 403 |

Routers compose them: `user = Depends(get_current_user)`, `admin = Depends(require_roles("admin"))`. Ownership checks live in services (they already load the ticket).

## 4. Error handling (`app/core/errors.py`)

```python
class AppError(Exception):
    code: str; status_code: int; message: str
    def __init__(self, message, *, details: list[dict] | None = None): ...

class NotFoundError(AppError):      code="NOT_FOUND";       status_code=404
class ForbiddenError(AppError):     code="FORBIDDEN";       status_code=403
class UnauthorizedError(AppError):  code="UNAUTHORIZED";    status_code=401
class ConflictError(AppError):      code="CONFLICT";        status_code=409
class InvalidTransitionError(AppError): code="INVALID_TRANSITION"; status_code=409
class ReopenWindowError(AppError):  code="REOPEN_WINDOW_EXPIRED"; status_code=409
```

`register_exception_handlers(app)`:
- `AppError` → `{"error": {"code", "message", "details"}}` with its status.
- `RequestValidationError` → 422 `VALIDATION_ERROR` with `details=[{"field": "body.title", "issue": "..."}]` (field names stripped of body/path prefixes).
- `StarletteHTTPException` → mapped (404 → NOT_FOUND envelope, etc.).
- catch-all `Exception` → 500 `INTERNAL_ERROR`, generic message; full traceback logged with `request_id`.

## 5. State machine (`app/services/status_machine.py`)

```python
TRANSITIONS: dict[TicketStatus, dict[TicketStatus, frozenset[UserRole]]] = {
    TicketStatus.OPEN:        {IN_PROGRESS: {AGENT, ADMIN}, ON_HOLD: {AGENT, ADMIN}},
    TicketStatus.IN_PROGRESS: {ON_HOLD: {AGENT, ADMIN}, RESOLVED: {AGENT, ADMIN}},
    TicketStatus.ON_HOLD:     {IN_PROGRESS: {AGENT, ADMIN}},
    TicketStatus.RESOLVED:    {CLOSED: {REQUESTER, AGENT, ADMIN}, REOPENED: {REQUESTER, AGENT, ADMIN}},
    TicketStatus.CLOSED:      {REOPENED: {REQUESTER, AGENT, ADMIN}},   # + reopen-window check
    TicketStatus.REOPENED:    {IN_PROGRESS: {AGENT, ADMIN}},
}

def validate_transition(ticket, to, user, settings) -> None:
    # raises InvalidTransitionError (allowed list in details) or ForbiddenError (role)
    # requester on RESOLVED/CLOSED transitions: ticket.requester_id must equal user.id
    # CLOSED→REOPENED: now - closed_at(from audit) <= settings.reopen_window_days else ReopenWindowError
```

`ticket_service.transition(db, ticket, to, user, note)`:
1. `validate_transition` (pre-checks).
2. Apply side effects per [WORKFLOWS §3.2](WORKFLOWS.md#32-side-effects) (first response, pause/resume incl. due-date shift, `resolved_at`).
3. Persist new status + touched columns; write `STATUS_CHANGED` audit; optional note as a comment.
4. `notification_service` per [WORKFLOWS §9](WORKFLOWS.md#9-notification-triggers).
5. `sla_service.check_and_persist_breaches(db, ticket, user)` on the updated row.
6. Commit (via request-scoped session teardown).

## 6. SLA service (`app/services/sla_service.py`)

```python
def compute_due_dates(created_at, priority, policies) -> (first_response_due_at, resolution_due_at)
def sla_state(ticket, now, threshold) -> SLAState            # WORKFLOWS §5.2 — pure, no DB
def effective_elapsed(ticket, now) -> timedelta              # now - created_at - total_paused (minus current hold)
def apply_resume(ticket, now) -> None                        # delta, total_paused_seconds, shift both due_at
def check_and_persist_breaches(db, ticket, actor | None) -> None
    # AT_RISK → notification SLA_AT_RISK (deduped)
    # breached & not sla_breached → sla_breached=True, audit SLA_BREACHED (actor_id NULL),
    #                               notifications SLA_BREACHED → assignee + requester
def scan_all_open(db) -> dict                                # powers POST /internal/sla-scan (idempotent: breach flag
                                                             # only flips false→true; SLA notifications deduped)
```

Serialized ticket schemas call `sla_state(...)` via a `computed_ticket_schema(ticket, settings)` helper so every read path returns a fresh `sla_state`.

## 7. Audit helper (`app/services/audit_service.py`)

```python
def record(db, *, actor: User | None, action: str, entity_type: str, entity_id: UUID,
           ticket_id: UUID | None = None, old_value: dict | None = None,
           new_value: dict | None = None) -> AuditLog
```

- Appends a row in the **current transaction** (no separate commit) — services must call it before returning.
- `actor=None` for system actions (`AUTO_ASSIGNED`, `SLA_BREACHED`); `actor_role` snapshot taken from the actor.
- Password fields are never accepted into old/new values (call sites pass nothing; enforced by the helper refusing to serialize keys named `password`/`hashed_password` — they raise in debug, are stripped in prod).
- The action constants live in `app/models/enums.py::AuditAction` (plain `str` constants matching [WORKFLOWS §7](WORKFLOWS.md#7-audit-log-actions)).

## 8. Repositories — conventions

- One module per aggregate; each function takes `db: Session` as the first arg and returns `Model | list | tuple[list, int]`.
- `ticket_repository.build_list_query(db, user, filters)` returns a `Select` with: visibility clause (requester → own only), filter clauses (status list, priority list, category, assignee incl. `null` sentinel, `q` → `ILIKE` on title/description, `sla_state` post-filter), sort mapping, and `.count()` companion — pagination applied in the router via `Page[T]`.
- Ticket number: `allocate_ticket_number(db) -> int` executes the `UPDATE counters ... RETURNING` and returns the value inside the caller's transaction.
- No business rules, no audit calls, no notifications — pure persistence.

## 9. Seed script (`app/db/seed.py`, run as `python -m app.db.seed`)

Idempotent (checks by email/name; safe to run repeatedly). Creates:

| Item | Detail |
|---|---|
| 6 categories | Hardware, Software, Network, Access & Accounts, Email, Other (all active) |
| 4 SLA policies | CRITICAL 60/240, HIGH 240/1440, MEDIUM 480/2880, LOW 1440/4320 |
| 1 admin | `admin@deskflow.dev` / `Admin@1234` — "Carla Mendes" |
| 3 agents | `agent1..3@deskflow.dev` / `Agent@1234` — Bruno Costa, Diogo Ferreira, Elena Rocha |
| 5 requesters | `requester1..5@deskflow.dev` / `Requester@1234` — Ana Silva et al. |
| ~40 tickets | Spread over the **last 45 days**, all statuses, all priorities, realistic IT titles ("VPN drops every 10 minutes", "Password reset for ERP", "Monitor flickering"), ~70% with an assignee, ~30% with comments (2–6 each, some internal notes), statuses/dates chosen so the set includes: ≥3 `BREACHED` open tickets, ≥3 `AT_RISK`, several ON_HOLD (with real `paused_at`/`total_paused_seconds`), resolved-on-time and resolved-late ones (for a lively SLA trend), and a few CLOSED within/outside the reopen window |
| audit + notifications | Derived from the ticket histories above (STATUS_CHANGED sequences, comments, assignments) so the audit log and bell are populated |

Counter starts at 1040 → seeded tickets run `TCK-1041`…. Every seeded ticket/audit row is created through the **same services** used by the API (not raw SQL) so behavior and audit entries stay consistent.

## 10. Alembic workflow

1. Local: edit models → `alembic revision --autogenerate -m "..."` (requires a migrated dev DB) → review the generated file (autogenerate misses enums defaults/trigger — hand-fix) → `alembic upgrade head`.
2. Never edit an applied revision; fix forward with a new one.
3. The initial migration `0001_initial.py` contains: all enums, all tables, all indexes/constraints, the `trg_audit_logs_immutable` trigger, the `('ticket', 1040)` counter row, and the 4 `sla_policies` rows (production-safe, idempotent seeding of those rows lives in the migration itself so prod matches local).
4. CI/CD: `deploy.yml` job `migrate` runs `alembic upgrade head` with `DATABASE_URL=$NEON_DATABASE_URL` (Neon **direct** endpoint) **before** deploying the API to Vercel ([DEPLOYMENT §6](DEPLOYMENT.md#6-migration-strategy)).
5. Tests do **not** use Alembic: `conftest.py` creates the schema with `Base.metadata.create_all` on a dedicated test database (fast, no migration drift); the migration itself is exercised manually + in the deploy pipeline.

## 11. App entrypoint (`app/main.py`)

```python
def create_app() -> FastAPI:
    app = FastAPI(title="DeskFlow API", version=settings.app_version,
                  docs_url="/docs",          # kept on in prod — the Swagger UI is part of the demo
                  redoc_url=None)
    configure_logging(app)
    app.add_middleware(CORSMiddleware, ...)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    limiter.install(app)                       # slowapi
    app.include_router(api_router)             # prefix /api/v1 (health lives inside: GET /api/v1/health)
    return app

app = create_app()
```

Run: `uvicorn app.main:app --reload --port 8000` (dev) / on Vercel the `@vercel/python` runtime imports the same `app` via the entrypoint `index.py` (`from app.main import app`) — no uvicorn in production.
