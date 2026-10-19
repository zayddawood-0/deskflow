# Demo Script — DeskFlow (3–5 minutes)

Audience: the ETL reviewer/interviewer. Goal: show the full lifecycle, the SLA engine, RBAC, and the admin surface — while dropping architecture talking points at natural pauses.

**Setup before the call:** production seeded (`python -m app.db.seed`), three browser profiles (or one browser + incognito) logged in as requester1 / agent1 / admin. Have `/dashboard` preloaded as admin. Total speaking time ≈ 4 minutes.

---

## Act 1 — Requester raises a ticket (~60 s)

1. **(Incognito) Log in as `requester1@deskflow.dev` / `Requester@1234`.** Land on `/tickets` — note the redirect: requesters never see the dashboard; they see their own queue. *"Everything is scoped server-side — another employee's ticket doesn't even 403, it 404s."*
2. Click **New ticket** → `/tickets/new`:
   - Title: "Wi-Fi disconnects every 10 minutes"
   - Description: a couple of realistic sentences
   - Category: **Network**, Priority: **HIGH**
   - Point at the helper text: *"HIGH means a 4-hour first response and 24-hour resolution — those targets come from the admin-configurable SLA policy table."*
   - Leave **auto-assign** on → Create.
3. On the ticket detail page (`/tickets/TCK-####`):
   - **SLA badge + live countdown** ticking toward `resolution_due_at`.
   - *"Due dates are computed at creation from the priority policy and stored in UTC; the backend also computes ON_TRACK/AT_RISK/BREACHED — the frontend only renders and ticks."*
   - The ticket already shows an **assignee** → auto-assignment picked the least-loaded active agent.
4. Add a **public comment**: "It happens mostly in meeting room B." → *"Comments notify the assignee; internal notes will never reach me."*

**Talking point:** *"The API rejects anything the process doesn't allow — invalid transitions return 409 with the allowed next statuses, and requesters can't even send is_public:false."*

## Act 2 — Agent works the queue (~90 s)

5. **Switch profile, log in as `agent1@deskflow.dev` / `Agent@1234`.** The bell already shows an unread count — assignment + comment notifications. *"30-second polling, no WebSocket in the MVP."*
6. `/tickets` → tab **My tickets**: the new ticket is at the top with an orange **In progress-ready** state. Click it.
7. **Internal note** (toggle Public → Internal): "Room B has the old AP — likely the culprit." → *"Agents collaborate privately; requesters can't see this anywhere — the API filters it out of every read path."*
8. Transition **OPEN → IN_PROGRESS** (button appears per the transition matrix) — the audit timeline immediately gets "STATUS_CHANGED" and `first_responded_at` is stamped.
9. **SLA pause demo:** transition **IN_PROGRESS → ON_HOLD** with note "Waiting for a replacement AP from storage." → countdown switches to **Paused**.
   - *"ON_HOLD freezes the clock: we store paused_at, accumulate total_paused_seconds, and on resume shift both due dates forward by exactly the paused duration. At 75% of any target the ticket flips to AT_RISK and notifies; a breach persists once, writes a SLA_BREACHED audit entry, and notifies the assignee and the requester."*
10. Resume **ON_HOLD → IN_PROGRESS**, then **IN_PROGRESS → RESOLVED** with note "Swapped AP, stable for 30 min."
11. (Optional, 20 s) Show the filter bar: status/priority/SLA-state filters, search, tabs My/Unassigned/All — *"the whole filter state lives in the URL, so queues are shareable."*

## Act 3 — Requester closes the loop (~45 s)

12. Back to **requester1**: bell shows "resolved" notification. Open the ticket → **Reopen ticket** (status RESOLVED → REOPENED):
    - *"Reopen is allowed from RESOLVED, or from CLOSED within 7 days — after that the API returns REOPEN_WINDOW_EXPIRED and the button is disabled with a tooltip. The original SLA due dates survive the reopen."*
13. Comment "Fixed for now, thanks!" → then **Close ticket** (RESOLVED → CLOSED — note it must be resolved again by an agent first if reopened; if you reopened, jump to admin instead of re-resolving to save time).
14. Point at the **timeline** at the bottom of the detail page: every event with actor, timestamp, old → new values. *"That's the same audit table the admin global log reads from — append-only, with a database trigger that physically blocks UPDATE and DELETE."*

## Act 4 — Admin: dashboard, audit, configuration (~75 s)

15. **Log in as `admin@deskflow.dev` / `Admin@1234`** → `/dashboard`:
    - KPI cards: Open, In progress, Resolved this week, and the **dark brown SLA Breaches card**.
    - Bar chart (tickets/day — recent bars orange, older beige), orange area line (SLA compliance trend), breakdowns, recent tickets table with status pills.
    - *"All five endpoints are computed live from the database — no denormalized analytics tables at this scale. resolved_this_week counts STATUS_CHANGED→RESOLVED audit entries, so reopens don't inflate it."*
    - Click a KPI → jumps into the pre-filtered ticket list.
16. `/audit`: filter by action = `STATUS_CHANGED`, pick today's ticket → show old/new chips. Then try a filter by actor.
    - *"Every mutation in the services writes its audit row in the same transaction — no change can commit unaudited."*
17. `/admin/sla`: change HIGH resolution from 1440 → 720 minutes, save, toast appears. *"Applies to new tickets only — existing due dates are historical facts."* (Change it back.)
18. `/admin/users`: show role dropdown + active toggle; mention deactivation revokes sessions but keeps history.
19. (15 s) **Failure demo:** with `curl` (or the local Swagger UI at `/docs`), attempt `POST /tickets/{id}/status` with `{"status": "CLOSED"}` on an `OPEN` ticket as agent → **409 INVALID_TRANSITION** with the allowed list. *"The state machine is server-side; the buttons are just its projection."*

## Closing line (~15 s)

> "FastAPI with a strict router→service→repository layering, sync SQLAlchemy and Alembic; Next.js App Router with TanStack Query and a token-based auth flow; every value in this demo comes from the docs in `/docs`, which are the source of truth — schema, API, workflows and this script stay in sync with the code. CI runs ruff, pytest and the full frontend build on every push; deploys migrate Neon first, then deploy the API and web as two Vercel projects."

---

## Backup talking points (use only if asked)

| Question | Answer in one breath |
|---|---|
| Why sync SQLAlchemy? | 1-day scope: sync keeps migrations, services and test fixtures simple; FastAPI runs it in a threadpool; the throughput is irrelevant at this scale. |
| Why polling instead of WebSockets? | Long-lived sockets fit poorly with stateless serverless functions, and polling is reliable under demo conditions; 30 s latency is acceptable for in-app notifications; WebSocket is the top stretch item. |
| Where is the SLA state stored? | Nowhere — `ON_TRACK/AT_RISK/BREACHED` is computed on every read; only the irreversible `sla_breached` flag is persisted (for KPIs and one-shot notifications). |
| How do you prevent SQL injection / XSS? | Parameterized SQLAlchemy everywhere; React escapes all rendered text; no HTML injection surface. |
| How is RBAC enforced? | Backend dependency (`require_roles`) + ownership checks + the transition matrix on every endpoint; the frontend guards are UX only. |
| What would you do next with more time? | Attachments, email notifications, WebSocket live updates, CSV export, SLA business-hours calendars — full list in the PRD's stretch section. |
