# PRD — DeskFlow: IT Helpdesk & Ticketing System

| | |
|---|---|
| **Product** | DeskFlow |
| **Owner** | Screening project — ETL Full Stack Web Developer internship |
| **Deadline** | Monday 19 October 2026 |
| **Scope** | MVP only; stretch items explicitly marked |
| **Related docs** | [ARCHITECTURE](ARCHITECTURE.md) · [DATABASE_SCHEMA](DATABASE_SCHEMA.md) · [API_SPEC](API_SPEC.md) · [WORKFLOWS](WORKFLOWS.md) · [FRONTEND_SPEC](FRONTEND_SPEC.md) · [TESTING](TESTING.md) · [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md) |

## 1. Problem

Small companies (10–200 people) handle internal IT support through a shared email inbox or a spreadsheet. That leads to:

- **Lost requests** — nobody owns a request; it sits unanswered.
- **No accountability** — nobody can answer "who changed this ticket's priority, and when?"
- **No SLA discipline** — urgent issues are not distinguished from routine ones, and response times are unknown.
- **No visibility** — management cannot see IT's workload, recurring problems or bottlenecks.

## 2. Goals (MVP)

| # | Goal | How we know it works |
|---|---|---|
| G1 | Employees can raise a ticket in < 30 s and track it to resolution | Requester can create, comment, close/reopen own tickets |
| G2 | Agents have a single queue with clear ownership | List with filters, self-assign, manual assign, auto-assign |
| G3 | Work follows an enforced process | Server-side state machine; invalid transitions rejected with 409 |
| G4 | SLA targets are visible and enforced | Live countdown, ON_TRACK/AT_RISK/BREACHED badges, pause on ON_HOLD, breach notifications |
| G5 | Every change is traceable | Append-only audit log; per-ticket timeline; global admin log |
| G6 | Admins can configure the system without code changes | Manage users/roles, categories, SLA policies |
| G7 | A reviewer understands the state of IT support in 5 seconds | Dashboard with KPI cards and charts |
| G8 | The whole thing is production-shaped | Auth + RBAC, tests, CI/CD to Neon/Render/Vercel |

## 3. Non-goals (explicitly out of MVP)

- Email/SMS/push notifications (in-app only).
- File attachments, image uploads.
- Real-time updates via WebSocket (polling is fine).
- Multi-tenant / multiple companies.
- Knowledge base / FAQ, customer satisfaction surveys.
- Business-hours calendars for SLA (24/7 clock; see stretch).
- LDAP/SSO/social login.
- Mobile apps (responsive web only).
- CSV/Excel export (stretch).

## 4. Personas

| Persona | Description | Primary needs |
|---|---|---|
| **Ana — Requester** (employee) | Non-technical marketing coordinator. Opens a ticket when her laptop won't boot or she loses access to a system. Checks status occasionally. | Easy ticket creation, clear status, ability to add info and reopen if the fix didn't work. Never sees internal agent notes. |
| **Bruno — Agent** (IT support) | One of 3 support agents. Lives in the ticket queue all day. | One queue with filters, fast self-assign, internal notes, SLA countdowns so he prioritizes breaches first. |
| **Carla — Admin** (IT manager) | Runs the IT function. Configures the tool and reports upward. | Dashboard, audit log, user/role management, SLA policy tuning, assignment control. |

## 5. User stories & acceptance criteria

Roles: `requester`, `agent`, `admin`. Statuses: `OPEN | IN_PROGRESS | ON_HOLD | RESOLVED | CLOSED | REOPENED`. Priorities: `LOW | MEDIUM | HIGH | CRITICAL`.

### 5.1 Auth & profile (all roles)

**US-A1 — Register.** As a visitor, I can register with email, full name and password so that I can log in.
- AC1.1: `POST /api/v1/auth/register` with a unique email, password ≥ 8 chars containing upper, lower and a digit creates a user with role `requester` and returns `201` with the user object (no token issued at registration).
- AC1.2: Duplicate email → `409` with code `CONFLICT`. Invalid payload → `422` with code `VALIDATION_ERROR` and per-field details.
- AC1.3: Frontend page `/register`; link to `/login` for existing users.

**US-A2 — Login.** As a registered user, I can log in with email + password.
- AC2.1: `POST /api/v1/auth/login` returns `{access_token, token_type: "bearer", expires_in, user}` and sets the refresh token as an httpOnly cookie (`Path=/api/v1/auth`) — the refresh token is never in the response body.
- AC2.2: Wrong credentials → `401 UNAUTHORIZED` with a generic message ("Invalid email or password") that does not reveal whether the email exists.
- AC2.3: Inactive user (`is_active=false`) → `401`.
- AC2.4: Login is rate-limited to 5 attempts/minute per IP → `429 RATE_LIMITED`.
- AC2.5: Frontend page `/login`; on success redirect to `/dashboard` (agent/admin) or `/tickets` (requester).

**US-A3 — Session.** As a logged-in user, my session survives page reloads and expires safely.
- AC3.1: Access token (30 min) is held in memory; the refresh token (14 days) is an httpOnly `SameSite=Lax` cookie scoped to `Path=/api/v1/auth` (set/cleared by the backend, invisible to JS; the browser talks to the API only same-origin through the Next.js rewrite proxy); on a `401` the client attempts one silent refresh via `POST /api/v1/auth/refresh` (empty body, cookie rides along) and retries, otherwise redirects to `/login`.
- AC3.2: Refresh rotates the refresh token (the old one is revoked) and issues a new pair; a revoked or expired refresh token → `401`.
- AC3.3: `POST /api/v1/auth/logout` revokes the presented refresh token → `204`.
- AC3.4: Token storage tradeoff is documented in [AUTH_AND_SECURITY §3](AUTH_AND_SECURITY.md#3-token-storage-frontend).

**US-A4 — Profile & password.** As a logged-in user, I can view my profile and change my password.
- AC4.1: `GET /api/v1/auth/me` returns the current user.
- AC4.2: `POST /api/v1/auth/change-password` with `{current_password, new_password}` → `204`; wrong current password → `401`; on success all other refresh tokens of that user are revoked.
- AC4.3: Frontend page `/settings` (all roles).

### 5.2 Requester

**US-R1 — Create ticket.** As a requester, I can raise a ticket so that IT can help me.
- AC1.1: `POST /api/v1/tickets` with `{title, description, category_id, priority, auto_assign}` (`auto_assign` defaults `true`) → `201` with the ticket including generated `ticket_number` (`TCK-1042` format), `status="OPEN"`, `sla_state`, `first_response_due_at`, `resolution_due_at`.
- AC1.2: Title 5–200 chars, description ≥ 10 chars, priority ∈ enum, category must exist and be active → else `422 VALIDATION_ERROR` with per-field details.
- AC1.3: `first_response_due_at = created_at + first_response_minutes(priority)` and `resolution_due_at = created_at + resolution_minutes(priority)` per the default SLA table (see [WORKFLOWS §5](WORKFLOWS.md#5-sla-calculation-algorithm)).
- AC1.4: With `auto_assign=true` and an active agent available, the ticket is assigned to the least-loaded active agent and `auto_assigned=true`; audit entries `TICKET_CREATED` (and `AUTO_ASSIGNED` when applicable) are written; a `TICKET_ASSIGNED` notification goes to the assignee.
- AC1.5: Frontend `/tickets/new` form (title, description, category select, priority select, auto-assign checkbox); on success redirect to `/tickets/[id]`.

**US-R2 — View own tickets.** As a requester, I can list and search my tickets.
- AC2.1: `GET /api/v1/tickets` as a requester returns **only tickets where requester_id = me**, enforced server-side; other users' tickets are invisible (existence not even revealed — `404` on foreign ticket detail).
- AC2.2: Filters `status`, `priority`, `category_id`, `q` (title/description search), `sort` (`-created_at` default; also `priority`, `due_at`), pagination envelope `{items, page, page_size, total, pages}`.
- AC2.3: Each row shows ticket_number, title, status pill, priority badge, SLA badge, `updated_at`.
- AC2.4: Frontend `/tickets` with a filter bar; requesters see no assignee-management controls.

**US-R3 — Discuss on own ticket.** As a requester, I can add information to my ticket.
- AC3.1: `POST /api/v1/tickets/{id}/comments` `{body}` (min 1 char) → `201`; `is_public` is always forced to `true` for requesters — sending `is_public: false` → `403 FORBIDDEN`.
- AC3.2: `GET /api/v1/tickets/{id}/comments` returns public comments only; internal notes are filtered out for requesters on every read path.
- AC3.3: Adding a public comment on a ticket that has an assignee sends that agent a `COMMENT_ADDED` notification.

**US-R4 — Reopen / close own ticket.** As a requester, I can reopen a resolved or recently closed ticket, or close a resolved one.
- AC4.1: `POST /api/v1/tickets/{id}/status` `{status: "REOPENED"}` is allowed when the current status is `RESOLVED`, or `CLOSED` **within 7 days** of closing (`REOPEN_WINDOW_DAYS`); outside the window → `409 REOPEN_WINDOW_EXPIRED`.
- AC4.2: `{status: "CLOSED"}` is allowed from `RESOLVED`. A requester may only act on tickets they own → else `404`/`403`.
- AC4.3: Reopen writes audit `STATUS_CHANGED` (old=`RESOLVED`, new=`REOPENED`), notifies the assignee, and the SLA clock resumes against the existing due dates.
- AC4.4: Frontend ticket detail shows "Close ticket" on `RESOLVED` and "Reopen ticket" on `RESOLVED`/`CLOSED` (disabled with a tooltip when outside the reopen window).

**US-R5 — See SLA countdown.** As a requester, I can see how much time is left so I know what to expect.
- AC5.1: Ticket detail shows a live countdown to `resolution_due_at` with an `ON_TRACK` / `AT_RISK` / `BREACHED` badge (backend-computed `sla_state`; the frontend only renders and ticks it).
- AC5.2: On `ON_HOLD` tickets the countdown shows "Paused" instead of a running timer.

### 5.3 Agent

**US-G1 — Work the queue.** As an agent, I can see unassigned tickets and tickets assigned to me, plus everything else in an "All" view.
- AC1.1: `GET /api/v1/tickets` as an agent returns all tickets; the default view preset filters `assignee_id=me OR assignee_id=null` client-side via two saved filter buttons (My tickets / Unassigned), not a special backend mode.
- AC1.2: An agent can open any ticket detail (`GET /api/v1/tickets/{id}`).
- AC1.3: Frontend `/tickets` shows tabs **My tickets · Unassigned · All** implemented as query-param presets.

**US-G2 — Self-assign.** As an agent, I can claim an unassigned ticket.
- AC2.1: `POST /api/v1/tickets/{id}/self-assign` on an unassigned ticket → `200`, `assignee = me`, audit `ASSIGNED` (actor=me, old=null, new=me).
- AC2.2: Already assigned to someone else → `409 CONFLICT`; already assigned to me → `409 ALREADY_ASSIGNED`.
- AC2.3: Notifies the requester with `TICKET_ASSIGNED`.

**US-G3 — Change status.** As an agent, I can move tickets through the workflow.
- AC3.1: `POST /api/v1/tickets/{id}/status` enforces the transition table in [WORKFLOWS §3](WORKFLOWS.md#3-transition-table). Agent-valid transitions: `OPEN→IN_PROGRESS`, `OPEN→ON_HOLD`, `IN_PROGRESS→ON_HOLD`, `ON_HOLD→IN_PROGRESS`, `IN_PROGRESS→RESOLVED`, `REOPENED→IN_PROGRESS`.
- AC3.2: Any other (from, to) pair → `409 INVALID_TRANSITION` with a message naming the allowed next statuses; a role that is not allowed for that transition → `403 FORBIDDEN`.
- AC3.3: Entering `IN_PROGRESS`, `ON_HOLD` or `RESOLVED` as an agent/admin sets `first_responded_at` when it is still null (first response).
- AC3.4: Entering `ON_HOLD` sets `paused_at`; leaving `ON_HOLD` adds the paused delta to `total_paused_seconds` and shifts both due dates forward by the same delta (SLA pause).
- AC3.5: Entering `RESOLVED` sets `resolved_at` when it is null and notifies the requester; entering `REOPENED` notifies the assignee.
- AC3.6: Frontend ticket detail renders only the buttons allowed by the transition table for the current user's role and current status.

**US-G4 — Change priority / category.** As an agent, I can correct the priority or category of a ticket.
- AC4.1: `PATCH /api/v1/tickets/{id}` with `{priority}` and/or `{category_id}` → `200`; audit `PRIORITY_CHANGED` (old/new) when priority changes.
- AC4.2: Invalid enum or inactive category → `422`.

**US-G5 — Comment & internal notes.** As an agent, I can reply to the requester and leave notes for colleagues.
- AC5.1: `POST /api/v1/tickets/{id}/comments` `{body, is_public: true}` → the requester gets a `COMMENT_ADDED` notification; the first public comment by an agent/admin sets `first_responded_at` when null and satisfies the first-response SLA.
- AC5.2: `{is_public: false}` creates an internal note: invisible to requesters in every read path, labeled "Internal note" in the UI for agents/admins.
- AC5.3: Internal notes never change `first_responded_at` and never notify the requester.
- AC5.4: The frontend comment box has a Public / Internal toggle, visible only to agents/admins.

**US-G6 — SLA visibility.** As an agent, I can prioritize by SLA.
- AC6.1: Ticket list supports filter `sla_state=ON_TRACK|AT_RISK|BREACHED` and a sort option by `due_at` ascending.
- AC6.2: Each row shows a compact SLA badge; the detail page shows the full countdown.

### 5.4 Admin (an admin can do everything an agent can)

**US-B1 — Assign / reassign.** As an admin, I can assign any ticket to any active agent.
- AC1.1: `POST /api/v1/tickets/{id}/assign` `{assignee_id}` (target must be an active user with role `agent` or `admin`) → `200`; audit `ASSIGNED` with old/new assignee; `TICKET_ASSIGNED` notification to the new assignee.
- AC1.2: Reassigning overwrites and writes audit with the old value; assigning to a non-agent or inactive user → `422`.
- AC1.3: `POST /api/v1/tickets/{id}/unassign` → `200`, audit `UNASSIGNED` (old=assignee, new=null).
- AC1.4: Frontend ticket detail has an assignee combobox (admin only).

**US-B2 — Manage users & roles.** As an admin, I can onboard people and change roles.
- AC2.1: `GET /api/v1/users` (filters: `role`, `is_active`, `q`, pagination); `POST /api/v1/users` `{email, full_name, password, role}` creates any role; `PATCH /api/v1/users/{id}` changes `full_name`, `role`, `is_active`; `DELETE /api/v1/users/{id}` deactivates (soft delete) and revokes that user's refresh tokens.
- AC2.2: Deactivated users cannot log in and their existing sessions die on the next refresh; historical tickets and audit entries remain intact (referenced by id).
- AC2.3: An admin cannot deactivate or demote themselves → `409 CONFLICT`.
- AC2.4: A role change writes audit `ROLE_CHANGED` (old/new).
- AC2.5: Frontend `/admin/users` — table with role select, active toggle, "New user" modal.

**US-B3 — Manage categories.** As an admin, I can maintain the category list.
- AC3.1: `GET /api/v1/categories`; `POST /api/v1/categories` `{name, description}`; `PATCH /api/v1/categories/{id}` `{name?, description?, is_active?}`; `DELETE /api/v1/categories/{id}` deactivates.
- AC3.2: Inactive categories cannot be chosen for new tickets (`422`); existing tickets keep their FK.
- AC3.3: Duplicate category name → `409`. Mutations write audit `CATEGORY_CREATED` / `CATEGORY_UPDATED` / `CATEGORY_DEACTIVATED`.
- AC3.4: Frontend `/admin/categories` — inline-editable table + create modal.

**US-B4 — Configure SLA policies.** As an admin, I can tune SLA targets per priority.
- AC4.1: `GET /api/v1/sla-policies` returns 4 rows (LOW/MEDIUM/HIGH/CRITICAL) with `first_response_minutes`, `resolution_minutes`.
- AC4.2: `PUT /api/v1/sla-policies/{priority}` `{first_response_minutes, resolution_minutes}` (both 1–10080, first ≤ resolution) → `200`; audit `SLA_POLICY_UPDATED` with old/new.
- AC4.3: Changes apply to **new** tickets only; existing tickets keep their stored due dates.
- AC4.4: Frontend `/admin/sla` — 4 cards with numeric inputs + save button; success toast.

**US-B5 — Audit log.** As an admin, I can answer "what happened, who did it, when?"
- AC5.1: `GET /api/v1/audit` (admin only) with filters `actor_id`, `action`, `entity_type`, `ticket_id`, `date_from`, `date_to`, pagination; each entry: `{id, actor, action, entity_type, entity_id, ticket_id, old_value, new_value, created_at}`.
- AC5.2: Entries can never be updated or deleted (append-only; a DB trigger rejects UPDATE/DELETE).
- AC5.3: Frontend `/audit` — filterable table; each ticket also embeds its own timeline via `GET /api/v1/tickets/{id}/audit`.

**US-B6 — Dashboard.** As an agent or admin, I can see the state of IT support at a glance.
- AC6.1: `GET /api/v1/dashboard/stats` → `open_tickets`, `in_progress`, `unassigned`, `resolved_this_week`, `sla_breaches`, `avg_first_response_minutes`, `avg_resolution_minutes`.
- AC6.2: `GET /api/v1/dashboard/tickets-per-day?days=30`, `GET /api/v1/dashboard/sla-trend?days=30` (compliance % = share of first resolutions that met the resolution target, per day), `GET /api/v1/dashboard/breakdown` (counts by priority and by category, open+in-progress tickets), `GET /api/v1/dashboard/recent-tickets?limit=8`.
- AC6.3: Frontend `/dashboard` renders: 4 KPI cards (Open, In progress, Resolved this week, SLA breaches — the last one as the dark brown highlighted card), a bar chart of tickets/day, an orange line chart with gradient fill for SLA compliance, two breakdown charts, and a recent-tickets table with status pills.
- AC6.4: Access: `agent`, `admin` only. A requester visiting `/dashboard` is redirected to `/tickets`.

**US-B7 — Notifications.** As any user, I am notified of events that concern me.
- AC7.1: Notifications are created for: assignment (`TICKET_ASSIGNED` → assignee), new public comment (`COMMENT_ADDED` → the requester when an agent/admin comments, → the assignee when the requester comments), resolution/reopen/close (`STATUS_CHANGED` → the counterpart party), SLA at risk and breached (`SLA_AT_RISK` / `SLA_BREACHED` → assignee; breached also → requester).
- AC7.2: `GET /api/v1/notifications` (paginated, `unread_only` param), `GET /api/v1/notifications/unread-count`, `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications/read-all`.
- AC7.3: Frontend bell in the navbar with an unread-count dot and a dropdown list; polls every 30 s (no WebSocket in MVP).
- AC7.4: Notifications are never created for inactive users, and requesters only receive notifications about their own tickets.

### 5.5 Cross-cutting

**US-X1 — RBAC.** Every endpoint checks the caller's role **and** resource ownership; the frontend additionally guards routes (redirects + hidden controls), but the backend is the source of truth. See the permission matrix in [AUTH_AND_SECURITY §4](AUTH_AND_SECURITY.md#4-rbac-permission-matrix).

**US-X2 — Errors.** Every non-2xx response uses the standard envelope `{"error": {"code", "message", "details"}}` (see [API_SPEC §2](API_SPEC.md#2-standard-envelopes)); the frontend maps `code` to a human-readable toast.

**US-X3 — Audit completeness.** Every mutation listed in [WORKFLOWS §7](WORKFLOWS.md#7-audit-log-actions) writes exactly one audit entry with actor, action, entity, old/new value and timestamp.

## 6. Stretch features (only after all MVP phases are ticked)

| # | Feature | Notes |
|---|---|---|
| S1 | File attachments on tickets/comments | S3-compatible storage + signed URLs; new `attachments` table |
| S2 | Email notifications | Transactional email API; templates for assign/comment/SLA |
| S3 | WebSocket live updates | Replace 30 s polling for notifications + ticket list |
| S4 | CSV export | Tickets list and audit log export endpoints + buttons |
| S5 | Dark mode | Token swap on the design-system layer |
| S6 | SLA business-hours calendar | Pause SLA clock outside 9–18; per-category overrides |
| S7 | Saved filters & report date ranges | Persist per-user filter presets |
| S8 | Merge duplicate tickets | Admin action linking tickets |

## 7. Success criteria (reviewer checklist)

The project succeeds if a reviewer can, in under 10 minutes:

1. Log in as **requester**, raise a ticket, see the SLA countdown start, and comment.
2. Log in as **agent**, see the ticket appear in the queue (auto-assigned), self-assign another, move one to `ON_HOLD` and **watch the SLA timer pause**, resolve it, and leave an internal note that a requester could never see.
3. Log in as **requester**, reopen the resolved ticket, then close it.
4. Log in as **admin**, see the dashboard with live KPIs and charts, filter the audit log to find who changed what, change an SLA policy, and reassign a ticket.
5. Observe that an invalid transition (e.g. `OPEN → CLOSED`) is rejected by the API, that a breached ticket is flagged and notified, and that the whole flow is reflected in the audit log.
6. Find the codebase clean and well organized: green CI, passing tests, docs in `/docs` matching the running app.
