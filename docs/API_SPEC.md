# API Specification — DeskFlow

## 1. Base conventions

Base URL (local): `http://localhost:8000` · **All endpoints are prefixed with `/api/v1`** (health included). Interactive docs: `/docs` (Swagger UI) and `/redoc`.

Browser traffic is **same-origin**: the Next.js app serves `/api/v1/*` and proxies to the backend via `rewrites()` (`BACKEND_URL`) — the browser never calls the API origin directly, so CORS is irrelevant for the app (it exists only for local direct-to-API testing).

Auth: `Authorization: Bearer <access_token>` (in-memory, JS-set) on every endpoint except where **Public** is listed. The **refresh token travels in an httpOnly cookie** (`Path=/api/v1/auth`) that the browser attaches automatically to the auth endpoints below — clients never see or send it manually. Roles: `requester`, `agent`, `admin`. An **agent** inherits requester powers (agents may also create tickets), an **admin** inherits agent powers.

All request/response bodies are `application/json`. All timestamps are ISO-8601 UTC with `Z`. List endpoints return the pagination envelope below; singleton/health endpoints return plain objects.

---

## 2. Standard envelopes

### 2.1 Error response (all non-2xx)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      { "field": "title", "issue": "String should have at least 5 characters" }
    ]
  }
}
```

| `code` | HTTP status | When |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Pydantic request validation failed (`details` lists per-field issues) |
| `UNAUTHORIZED` | 401 | Missing/invalid/expired access token; bad credentials; revoked refresh token |
| `FORBIDDEN` | 403 | Role not allowed (e.g. requester setting `is_public: false`, non-admin hitting `/users`) |
| `NOT_FOUND` | 404 | Entity missing, or hidden by permissions (foreign ticket) |
| `CONFLICT` | 409 | Duplicate email/category, `ALREADY_ASSIGNED`, admin self-deactivation |
| `INVALID_TRANSITION` | 409 | Status transition not allowed by the state machine (`details[0].issue` lists allowed next statuses) |
| `REOPEN_WINDOW_EXPIRED` | 409 | Attempt to reopen a `CLOSED` ticket older than `REOPEN_WINDOW_DAYS` |
| `RATE_LIMITED` | 429 | Too many login attempts (slowapi); `Retry-After` header set |
| `INTERNAL_ERROR` | 500 | Unhandled server error (generic message; details only in server logs) |

### 2.2 Pagination envelope (list endpoints)

Request query params: `page` (≥1, default `1`), `page_size` (1–100, default `20`), plus resource-specific filters and `sort` (`field` = ascending, `-field` = descending).

```json
{
  "items": [ { "...": "resource objects" } ],
  "page": 1,
  "page_size": 20,
  "total": 57,
  "pages": 3
}
```

### 2.3 Shared object shapes

**User (public projection):**

```json
{
  "id": "0f1d5f9e-5a7c-4c2e-9a67-1b2c3d4e5f60",
  "email": "ana@acme.dev",
  "full_name": "Ana Silva",
  "role": "requester",
  "is_active": true,
  "created_at": "2026-10-17T08:00:00Z"
}
```

**Ticket:**

```json
{
  "id": "2a5f2c7e-1111-4a11-8a11-0d1e2f3a4b5c",
  "ticket_number": "TCK-1042",
  "title": "Laptop will not boot past BIOS",
  "description": "Blue screen with INACCESSIBLE_BOOT_DEVICE after Tuesday's update.",
  "status": "IN_PROGRESS",
  "priority": "HIGH",
  "category": { "id": "9c1a...f1", "name": "Hardware" },
  "requester": { "id": "0f1d...f60", "full_name": "Ana Silva", "email": "ana@acme.dev", "role": "requester" },
  "assignee": { "id": "77aa...b3", "full_name": "Bruno Costa", "email": "agent1@deskflow.dev", "role": "agent" },
  "auto_assigned": true,
  "first_response_due_at": "2026-10-17T12:00:00Z",
  "resolution_due_at": "2026-10-18T08:00:00Z",
  "first_responded_at": "2026-10-17T09:23:11Z",
  "resolved_at": null,
  "paused_at": null,
  "total_paused_seconds": 0,
  "sla_state": "ON_TRACK",
  "sla_breached": false,
  "created_at": "2026-10-17T08:00:00Z",
  "updated_at": "2026-10-17T09:23:11Z"
}
```

- `sla_state` (`ON_TRACK|AT_RISK|BREACHED`) is **computed on read**, never stored ([WORKFLOWS §5](WORKFLOWS.md#5-sla-calculation-algorithm)).
- `requester`/`assignee` are nested public projections; `assignee` is `null` when unassigned.

**Comment:**

```json
{
  "id": "bb1f...9d",
  "ticket_id": "2a5f...b5c",
  "author": { "id": "77aa...b3", "full_name": "Bruno Costa", "role": "agent" },
  "body": "Re-seated the RAM and the machine boots now.",
  "is_public": true,
  "created_at": "2026-10-17T09:23:11Z"
}
```

**Audit entry:**

```json
{
  "id": "cc9d...2e",
  "actor": { "id": "77aa...b3", "full_name": "Bruno Costa", "role": "agent" },
  "action": "STATUS_CHANGED",
  "entity_type": "ticket",
  "entity_id": "2a5f...b5c",
  "ticket_id": "2a5f...b5c",
  "old_value": { "status": "IN_PROGRESS" },
  "new_value": { "status": "ON_HOLD" },
  "created_at": "2026-10-17T10:02:44Z"
}
```

**Notification:**

```json
{
  "id": "dd0e...7a",
  "type": "TICKET_ASSIGNED",
  "title": "You were assigned TCK-1042",
  "body": "Laptop will not boot past BIOS · HIGH",
  "ticket_id": "2a5f...b5c",
  "is_read": false,
  "created_at": "2026-10-17T08:00:01Z"
}
```

---

## 3. Health

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/v1/health` | Public | Liveness + DB check (uptime check; pinged every 15 min by `scheduled.yml`) |

**`GET /api/v1/health` → 200**

```json
{ "status": "ok", "database": "up", "version": "1.0.0" }
```

`database` is `down` → 503 with the same shape.

---

## 4. Auth (`/api/v1/auth`)

| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/auth/register` | Public | Self-registration (always role `requester`) |
| POST | `/auth/login` | Public | Email + password → access token + user; sets refresh cookie |
| POST | `/auth/refresh` | Public | Rotate the cookie's refresh token → new access token (+ rotated cookie) |
| POST | `/auth/logout` | Any authenticated | Revoke a refresh token |
| GET | `/auth/me` | Any authenticated | Current user |
| POST | `/auth/change-password` | Any authenticated | Change password, revoke other sessions |

### POST `/auth/register` → 201

Request:

```json
{ "email": "ana@acme.dev", "full_name": "Ana Silva", "password": "Requester@1234" }
```

Response: `201` with the [User](#23-shared-object-shapes) object (no token).

Errors: `409 CONFLICT` (email exists), `422 VALIDATION_ERROR`.

### POST `/auth/login` → 200 (rate-limited: 5/min per IP)

Request:

```json
{ "email": "ana@acme.dev", "password": "Requester@1234" }
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": { "id": "0f1d...f60", "email": "ana@acme.dev", "full_name": "Ana Silva", "role": "requester", "is_active": true, "created_at": "2026-10-17T08:00:00Z" }
}
```

Sets the refresh cookie: `Set-Cookie: refresh_token=rt_...; HttpOnly; SameSite=Lax; Path=/api/v1/auth; Max-Age=1209600` (+ `Secure` when `APP_ENV=production`). The token itself is **not** in the body.
Errors: `401 UNAUTHORIZED` ("Invalid email or password."), `401` inactive account, `429 RATE_LIMITED`.

### POST `/auth/refresh` → 200

Request body: empty (`{}`). The refresh token is read from the httpOnly cookie (the browser attaches it automatically because of `Path=/api/v1/auth`).
Response: same shape as login (new access token + `expires_in` + user) and a **rotated** refresh cookie (`Set-Cookie` again; the old row is revoked).
Errors: `401 UNAUTHORIZED` (cookie missing, unknown, expired or revoked).

### POST `/auth/logout` → 204

Request body: empty (`{}`). Revokes the cookie's refresh token (idempotent → `204` even if already revoked) and clears the cookie: `Set-Cookie: refresh_token=; HttpOnly; SameSite=Lax; Path=/api/v1/auth; Max-Age=0`.

### GET `/auth/me` → 200

Response: [User](#23-shared-object-shapes). Errors: `401`.

### POST `/auth/change-password` → 204

Request: `{ "current_password": "...", "new_password": "..." }`.
Side effects: all refresh tokens of the user except the caller's current one are revoked; audit `PASSWORD_CHANGED` (actor = self, no values stored).
Errors: `401` (wrong current password), `422` (policy not met).

---

## 5. Users (`/api/v1/users`) — admin only

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/users` | admin | List/filter users |
| POST | `/users` | admin | Create a user with any role |
| GET | `/users/{user_id}` | admin | Fetch one |
| PATCH | `/users/{user_id}` | admin | Update name/role/active |
| DELETE | `/users/{user_id}` | admin | Deactivate (soft) + revoke sessions |

### GET `/users`

Query: `role`, `is_active` (`true|false`), `q` (email/name substring), `page`, `page_size`, `sort` (`full_name`, `email`, `created_at`, `-created_at` default).
Response: `200` pagination envelope of [User](#23-shared-object-shapes).

### POST `/users` → 201

Request: `{ "email": "new@deskflow.dev", "full_name": "New Agent", "password": "Agent@1234", "role": "agent" }` → `201` User. Audit `USER_CREATED`.
Errors: `409` duplicate email, `422` weak password / bad role.

### GET `/users/{user_id}` → 200 User · `404 NOT_FOUND`

### PATCH `/users/{user_id}` → 200 User

Request (all optional): `{ "full_name": "...", "role": "admin", "is_active": false }`.
Side effects: role change → audit `ROLE_CHANGED` `{"role":"agent"}` → `{"role":"admin"}`; deactivating → revoke refresh tokens + audit `USER_DEACTIVATED`.
Errors: `409 CONFLICT` when an admin demotes/deactivates **themselves**.

### DELETE `/users/{user_id}` → 204

Equivalent to `PATCH {is_active: false}`; revokes refresh tokens; audit `USER_DEACTIVATED`.
Errors: `409` self-deactivation, `404`.

---

## 6. Categories (`/api/v1/categories`)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/categories` | Any authenticated | List (incl. inactive for admin — param `include_inactive=true`) |
| POST | `/categories` | admin | Create |
| PATCH | `/categories/{category_id}` | admin | Update |
| DELETE | `/categories/{category_id}` | admin | Deactivate |

**Category object:** `{ "id": "...", "name": "Hardware", "description": "Laptops, monitors, peripherals", "is_active": true, "created_at": "..." }`

- `GET` default returns `is_active=true` rows only, sorted by `name`.
- `POST` `{ "name": "Peripherals", "description": "..." }` → `201`; audit `CATEGORY_CREATED`; `409` duplicate name.
- `PATCH` `{ "name"?, "description"?, "is_active"? }` → `200`; audit `CATEGORY_UPDATED` (old/new of changed fields).
- `DELETE` → `204`, sets `is_active=false`; audit `CATEGORY_DEACTIVATED`; tickets keep their FK. `404` if already inactive.

---

## 7. SLA policies (`/api/v1/sla-policies`)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/sla-policies` | Any authenticated | The 4 priority policies |
| PUT | `/sla-policies/{priority}` | admin | Replace targets for one priority |

**SLA policy object:**

```json
{ "priority": "HIGH", "first_response_minutes": 240, "resolution_minutes": 1440, "updated_at": "2026-10-17T07:00:00Z" }
```

`GET` → `200` with `{"items": [LOW, MEDIUM, HIGH, CRITICAL]}` (plain array envelope `{items:[...]}` without pagination).

`PUT /sla-policies/HIGH` body `{ "first_response_minutes": 240, "resolution_minutes": 1440 }` → `200` policy. Validation: 1–10080 and `first_response_minutes ≤ resolution_minutes` else `422`; audit `SLA_POLICY_UPDATED` old/new. Changes affect **new tickets only**.

---

## 8. Tickets (`/api/v1/tickets`)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/tickets` | requester, agent, admin | List with filters (requester: own only) |
| POST | `/tickets` | requester, agent, admin | Create ticket |
| GET | `/tickets/{ticket_id}` | requester (own), agent, admin | Detail |
| PATCH | `/tickets/{ticket_id}` | requester (own, OPEN/REOPENED), agent, admin | Edit title/description; agent/admin also priority/category |
| POST | `/tickets/{ticket_id}/status` | see transition table | State-machine transition |
| POST | `/tickets/{ticket_id}/self-assign` | agent, admin | Claim an unassigned ticket |
| POST | `/tickets/{ticket_id}/assign` | admin | Assign to another user |
| POST | `/tickets/{ticket_id}/unassign` | admin | Clear assignee |
| GET | `/tickets/{ticket_id}/comments` | requester (own), agent, admin | List comments (requester: public only) |
| POST | `/tickets/{ticket_id}/comments` | requester (own), agent, admin | Add comment / internal note |
| GET | `/tickets/{ticket_id}/audit` | requester (own), agent, admin | Per-ticket timeline |

### GET `/tickets`

Query params:

| Param | Type | Notes |
|---|---|---|
| `status` | repeatable/csv | `OPEN,IN_PROGRESS,...` (comma-separated) |
| `priority` | csv | `LOW,MEDIUM,HIGH,CRITICAL` |
| `category_id` | uuid | |
| `assignee_id` | uuid | special value `null` = unassigned |
| `sla_state` | single | `ON_TRACK\|AT_RISK\|BREACHED` (computed) |
| `q` | string | case-insensitive substring of title/description |
| `sort` | string | `-created_at` (default), `created_at`, `priority`, `due_at`, `updated_at` |
| `tab` | string | UI preset shortcut: `mine` (assignee=me), `unassigned`, `all` — resolved server-side to the equivalent assignee filter |
| `page`, `page_size` | int | envelope defaults 1 / 20 |

Response `200`: pagination envelope of [Ticket](#23-shared-object-shapes).
Visibility: requester → `requester_id = me`; agent/admin → all tickets.
Errors: `401`, `422` (bad enum/uuid).

### POST `/tickets` → 201

Request:

```json
{
  "title": "Laptop will not boot past BIOS",
  "description": "Blue screen with INACCESSIBLE_BOOT_DEVICE after Tuesday's update. Tried two restarts.",
  "category_id": "9c1a...f1",
  "priority": "HIGH",
  "auto_assign": true
}
```

Response `201`: Ticket (status `OPEN`, due dates set, `sla_state` computed).
Side effects: ticket-number allocation; due dates from `sla_policies`; optional auto-assignment ([WORKFLOWS §6](WORKFLOWS.md#6-auto-assignment)); audit `TICKET_CREATED` (+`AUTO_ASSIGNED`); `TICKET_ASSIGNED` notification.
Errors: `422` (title/description/priority/category), `404` (unknown category), `409` (inactive category).

### GET `/tickets/{ticket_id}` → 200 Ticket

Errors: `404 NOT_FOUND` for requester when the ticket belongs to someone else (existence not revealed), `401`.

### PATCH `/tickets/{ticket_id}` → 200 Ticket

Request (all optional): `{ "title"?, "description"?, "priority"?, "category_id"? }`.

| Field | requester | agent/admin |
|---|---|---|
| `title`, `description` | own ticket **and** status ∈ {OPEN, REOPENED} | any |
| `priority`, `category_id` | never (ignore → `422` if supplied) | any |

Side effects: priority change → audit `PRIORITY_CHANGED`; category change → audit `CATEGORY_CHANGED`; requester edit → audit `TICKET_UPDATED`.
Errors: `403` (wrong role/field), `409` (requester editing a ticket that moved on), `422`, `404`.

### POST `/tickets/{ticket_id}/status` → 200 Ticket

Request: `{ "status": "IN_PROGRESS", "note": "optional free text stored as a public comment" }`.
Allowed transitions + roles: [WORKFLOWS §3](WORKFLOWS.md#3-transition-table). `note` (≤1000 chars), when present, is stored as a comment by the caller (respecting their role: agents/admins → public comment; requester → public comment) and triggers first-response rules.

Errors:
- `409 INVALID_TRANSITION` — message + `details[0].issue = "Allowed next statuses: IN_PROGRESS, ON_HOLD"`.
- `403 FORBIDDEN` — role not permitted for this transition (e.g. requester → `IN_PROGRESS`).
- `404 NOT_FOUND` — unknown ticket or requester not the owner.
- `409 REOPEN_WINDOW_EXPIRED` — `CLOSED → REOPENED` outside `REOPEN_WINDOW_DAYS`.

Side effects (per transition): [WORKFLOWS §3.2](WORKFLOWS.md#32-side-effects) — audit `STATUS_CHANGED`, `first_responded_at`, `resolved_at`, pause/resume handling, notifications.

### POST `/tickets/{ticket_id}/self-assign` → 200 Ticket

Errors: `409 CONFLICT` (assigned to someone else), `409 ALREADY_ASSIGNED` (yours already), `404` (agent cannot see? — no: agents see all; only unknown id gives 404).
Side effects: `assignee = current user`; audit `ASSIGNED` (old `null`, new = me). Assignment notifications follow one rule everywhere (self-assign, admin assign, auto-assign, unassign): **notify the new assignee unless they are the actor, and always notify the requester** (type `TICKET_ASSIGNED`; for unassign the requester gets title "TCK-#### was unassigned").

### POST `/tickets/{ticket_id}/assign` → 200 Ticket (admin)

Request: `{ "assignee_id": "uuid" }`. Target must be `is_active=true` and role ∈ {agent, admin}.
Errors: `422` (non-agent/inactive target), `404`, `403` (non-admin).
Side effects: audit `ASSIGNED` with `old_value: {"assignee_id": ...}` / `new_value: {...}`; notifications per rule above.

### POST `/tickets/{ticket_id}/unassign` → 200 Ticket (admin)

Side effects: `assignee_id = null`, `auto_assigned = false`; audit `UNASSIGNED`; `TICKET_ASSIGNED` notification to the requester (title: "TCK-#### was unassigned").

### GET `/tickets/{ticket_id}/comments` → 200

```json
{ "items": [ { "...": "Comment" } ], "page": 1, "page_size": 50, "total": 4, "pages": 1 }
```

Query: `page`, `page_size` (default 50, sorted `created_at` ascending).
Visibility: requester sees only `is_public=true`; agent/admin see all. Internal notes are **never** serialized to requesters.

### POST `/tickets/{ticket_id}/comments` → 201 Comment

Request: `{ "body": "Please attach a screenshot of the error.", "is_public": true }` (`is_public` default `true`; body 1–5000 chars).

- requester: `is_public` must be `true` → else `403 FORBIDDEN`.
- agent/admin: `is_public=false` creates an internal note (audit `INTERNAL_NOTE_ADDED`; no notification to the requester; does **not** set `first_responded_at`).
- First public comment by agent/admin: sets `first_responded_at` when null; audit `COMMENT_ADDED`; `COMMENT_ADDED` notification to the requester. Requester public comment on an assigned ticket: audit `COMMENT_ADDED`; `COMMENT_ADDED` notification to the assignee.

Errors: `404`, `403`, `422`.

### GET `/tickets/{ticket_id}/audit` → 200

Pagination envelope of [Audit entry](#23-shared-object-shapes) filtered to this ticket, `sort=-created_at` (newest first). Same visibility as the ticket itself.

---

## 9. Audit log (`/api/v1/audit`) — admin only

### GET `/audit` → 200

Query: `actor_id`, `action` (e.g. `STATUS_CHANGED`), `entity_type` (`ticket|user|category|sla_policy`), `ticket_id`, `date_from`, `date_to` (ISO dates), `page`, `page_size`, `sort` (`-created_at` default).
Response: pagination envelope of [Audit entry](#23-shared-object-shapes).
Errors: `401`, `403` (non-admin).

Audit actions reference: [WORKFLOWS §7](WORKFLOWS.md#7-audit-log-actions).

---

## 10. Dashboard (`/api/v1/dashboard`) — roles: `agent`, `admin`

All endpoints return `403 FORBIDDEN` for `requester`.

### GET `/dashboard/stats` → 200

```json
{
  "open_tickets": 7,
  "in_progress": 12,
  "unassigned": 3,
  "resolved_this_week": 9,
  "sla_breaches": 4,
  "avg_first_response_minutes": 96,
  "avg_resolution_minutes": 1240
}
```

Definitions: `open_tickets` = status `OPEN`; `in_progress` = status `IN_PROGRESS`; `unassigned` = `assignee_id IS NULL` and status ∈ {OPEN, IN_PROGRESS, REOPENED}; `resolved_this_week` = audit entries `STATUS_CHANGED` with `new_value->>'status' = 'RESOLVED'` in the last 7 days; `sla_breaches` = tickets with `sla_breached = true` created in the last 30 days; `avg_first_response_minutes` = average of `first_responded_at − created_at` (minus paused time) over tickets with `first_responded_at` set; `avg_resolution_minutes` = average of `resolved_at − created_at` (minus paused time) over resolved tickets whose `resolved_at` is within the last 30 days (guards against seed outliers).

### GET `/dashboard/tickets-per-day?days=30` → 200

```json
{ "items": [ { "date": "2026-09-18", "count": 3 }, { "date": "2026-09-19", "count": 5 } ] }
```

`days` ∈ 7–90, default 30. Days with zero tickets are included (`count: 0`).

### GET `/dashboard/sla-trend?days=30` → 200

```json
{ "items": [ { "date": "2026-09-18", "compliance_pct": 88.5, "resolved": 6, "breached": 1 } ] }
```

`compliance_pct = round(100 * (resolved - breached_with_late_resolution) / resolved, 1)` for tickets whose `resolved_at` falls on that date; `0` resolutions → `compliance_pct: null`.

### GET `/dashboard/breakdown` → 200

```json
{
  "by_priority": [ { "priority": "CRITICAL", "count": 2 }, { "priority": "HIGH", "count": 6 }, { "priority": "MEDIUM", "count": 9 }, { "priority": "LOW", "count": 4 } ],
  "by_category": [ { "category": "Hardware", "count": 8 }, { "category": "Network", "count": 5 } ]
}
```

Scope: tickets with status ∈ {OPEN, IN_PROGRESS, ON_HOLD, REOPENED}; all four priorities always present (zero-filled); categories with zero open tickets omitted.

### GET `/dashboard/recent-tickets?limit=8` → 200

```json
{ "items": [ { "...": "Ticket" } ] }
```

`limit` 1–25, sorted `-created_at`, computed `sla_state` included (drives the status pills + badges in the table).

---

## 11. Notifications (`/api/v1/notifications`)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/notifications` | Any authenticated | Own notifications (paginated) |
| GET | `/notifications/unread-count` | Any authenticated | `{ "count": 3 }` |
| POST | `/notifications/{notification_id}/read` | Any authenticated | Mark one read → `204` |
| POST | `/notifications/read-all` | Any authenticated | Mark all read → `204` |

- `GET /notifications` query: `unread_only=true`, `page`, `page_size`, `sort=-created_at`. Scoped to the caller (never another user's) → `404` for foreign ids.
- `unread-count` → `200 { "count": 3 }` (used by the bell; polled every 30 s by the frontend).

---

## 12. Internal (`/api/v1/internal`)

### POST `/api/v1/internal/sla-scan`

Header: `X-Internal-Token: <INTERNAL_TASK_TOKEN>` (constant-time compare against the backend env var; wrong/missing → `403 FORBIDDEN`).

Invoked by `.github/workflows/scheduled.yml` every 15 minutes (cron + `workflow_dispatch`), which also pings `/api/v1/health`. The same detection additionally runs on ticket reads/mutations, so the scan only catches tickets nobody is looking at.

**Idempotent by construction:** the breach flag is only flipped `false → true` (one audit row per ticket, ever); at-risk/breached notifications are skipped when a notification of the same `(user, type, ticket)` already exists — running the scan twice in a row changes nothing the second time.

Response `200`:

```json
{ "scanned": 41, "newly_breached": 2, "at_risk": 3, "notifications_created": 4 }
```

Side effects: persists `sla_breached = true` for newly breached tickets (audit `SLA_BREACHED`, `actor_id = NULL` = system) and creates `SLA_AT_RISK` / `SLA_BREACHED` notifications per [WORKFLOWS §9](WORKFLOWS.md#9-notification-triggers).

---

## 13. Endpoint ↔ feature traceability

| Feature (PRD) | Endpoints |
|---|---|
| US-A1..A4 auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`, `POST /auth/change-password` |
| US-R1 create | `POST /tickets` |
| US-R2 list | `GET /tickets` |
| US-R3 comments | `GET/POST /tickets/{id}/comments` |
| US-R4 reopen/close | `POST /tickets/{id}/status` |
| US-R5 SLA view | `GET /tickets/{id}` (`sla_state`, `*_due_at`), `GET /tickets` (`sla_state` filter) |
| US-G1..G2 queue/self-assign | `GET /tickets?tab=`, `POST /tickets/{id}/self-assign` |
| US-G3 status | `POST /tickets/{id}/status` |
| US-G4 priority | `PATCH /tickets/{id}` |
| US-B1 assign | `POST /tickets/{id}/assign`, `/unassign` |
| US-B2 users | `GET/POST/PATCH/DELETE /users`, `GET /users/{id}` |
| US-B3 categories | `GET/POST/PATCH/DELETE /categories` |
| US-B4 SLA policies | `GET /sla-policies`, `PUT /sla-policies/{priority}` |
| US-B5 audit | `GET /audit`, `GET /tickets/{id}/audit` |
| US-B6 dashboard | `GET /dashboard/stats`, `/tickets-per-day`, `/sla-trend`, `/breakdown`, `/recent-tickets` |
| US-B7 notifications | `GET /notifications`, `/unread-count`, `POST /notifications/{id}/read`, `/read-all` |
| Health | `GET /api/v1/health` |
