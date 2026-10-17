# Implementation Plan — DeskFlow (1-day build)

**Deadline:** submit Monday 19 Oct 2026. **Rule:** work top-to-bottom, tick every box in the same session it is completed; never start a later phase while an earlier one has unticked MVP tasks. Anything in the **Cut list** (§9) is dropped first when the schedule slips — never a core MVP item.

Time boxes assume ~half-day blocks; the order is chosen so there is always a **deployable, demo-able** version at the end of every phase.

## Phase 1 — Scaffold & pipeline (first ~2 h)

- [ ] 1.1 Create monorepo skeleton: `frontend/`, `backend/`, `docs/`, `.github/workflows/`, root `README.md`, `AGENTS.md`, `docker-compose.yml` (db service only), `.gitignore` (Python+Node+`.env*`)
- [ ] 1.2 Backend skeleton: venv + `requirements.txt`/`requirements-dev.txt` pinned, `app/main.py` with `create_app()`, `GET /health` returning `{status, database, version}`, `app/core/config.py` (pydantic-settings), CORS, JSON logging + request-id middleware
- [ ] 1.3 Alembic initialized (`alembic.ini`, `env.py` wiring `Base.metadata`); empty DB migrated against Docker Postgres
- [ ] 1.4 Frontend skeleton: `create-next-app` (TS strict, Tailwind, App Router, `src/`), Manrope via `next/font`, design tokens in `tailwind.config.ts` + `globals.css` (copy from DESIGN_SYSTEM §1), base UI primitives: `Button`, `IconButton`, `Card`, `Input`, `Skeleton`
- [ ] 1.5 `frontend/src/lib/api-client.ts` (base URL, Bearer, refresh-once, `ApiError`) + `types/api.ts` envelopes + `constants.ts` enums
- [ ] 1.6 CI: `.github/workflows/ci.yml` as in DEPLOYMENT §5.1; push branch, confirm **green** (health test included: `test_health.py`)
- [ ] 1.7 `docker compose up --build` sanity check (all three services); revert to db-only dev mode

## Phase 2 — Data model, auth, RBAC (~3 h)

- [ ] 2.1 Models for ALL tables + enums (`app/models/*`) mirroring DATABASE_SCHEMA; initial Alembic revision `0001_initial` (tables, indexes, audit immutability trigger, `sla_policies` + counter seed rows) — one revision for the whole schema
- [ ] 2.2 `app/db/session.py`, `get_db`, transaction discipline; `tests/conftest.py` (test DB + rollback fixtures + `factories.py`)
- [ ] 2.3 `core/security.py` (argon2, JWT create/decode, refresh-token opaque + hash) + `core/errors.py` (AppError hierarchy + handlers producing the error envelope) + `core/rate_limit.py` (slowapi on login/register)
- [ ] 2.4 `auth_service` + `routers/auth.py`: register, login, refresh (rotation), logout, me, change-password — with `test_auth.py` passing
- [ ] 2.5 `users` endpoints (admin) + `require_roles` dep + `routers/users.py` — `test_rbac.py` core cases green (403 matrix, self-demotion 409, deactivated token death)
- [ ] 2.6 Frontend auth: `AuthProvider` (memory access + localStorage refresh), `use-auth`, `/login`, `/register`, `/settings` (profile + change password), `middleware.ts` redirects, `(app)/layout.tsx` shell with Navbar/IconRail placeholders
- [ ] 2.7 Categories + SLA-policy endpoints (read for all, write admin) + seed rows visible via API; `test_categories_and_sla.py` minimal set

## Phase 3 — Tickets, workflow, assignment, audit (~4 h)

- [ ] 3.1 `ticket_repository` (list query: visibility, filters, sort, pagination, `allocate_ticket_number`) + `ticket_service.create` (due dates from policies, audit `TICKET_CREATED`)
- [ ] 3.2 `status_machine.py` + `ticket_service.transition` with all side effects (first response, pause/resume, resolved_at, audit, notifications) — `test_transitions.py` fully green (valid + invalid + role + reopen-window matrices)
- [ ] 3.3 `assignment_service` (least-loaded pick, self-assign, admin assign/unassign, notifications) — `test_assignment.py` green
- [ ] 3.4 `audit_service.record` used by every mutation above; `GET /tickets/{id}/audit` + global `GET /audit` — `test_audit.py` green
- [ ] 3.5 Tickets endpoints complete: `GET/POST/PATCH /tickets`, `/status`, `/self-assign`, `/assign`, `/unassign` — `test_tickets.py` green
- [ ] 3.6 Frontend tickets: `use-tickets` hooks, `/tickets` list (DataTable, filters + URL sync, tabs), `/tickets/new` form (RHF+Zod), `/tickets/[id]` shell with status buttons + assignee combobox + timeline (comments land in Phase 4)

## Phase 4 — SLA engine, comments, notifications (~3 h)

- [ ] 4.1 `sla_service`: `compute_due_dates`, pure `sla_state`, `apply_resume`, `check_and_persist_breaches` (flag + audit + notifications, dedup) — `test_sla.py` green incl. worked examples A–D
- [ ] 4.2 Wire `sla_state` into every ticket serialization (list/detail/recent); `sla_state` list filter + `due_at` sort
- [ ] 4.3 `comment_service` + comments endpoints with visibility rules and first-response effects — `test_comments.py` green (internal notes invisible to requesters)
- [ ] 4.4 `notification_service` + notifications endpoints (`list`, `unread-count`, `read`, `read-all`) — `test_notifications.py` green
- [ ] 4.5 `internal/sla-scan` endpoint + `test_sla_scan` case
- [ ] 4.6 Frontend: comment list/form with Public/Internal toggle, `SlaBadge` + live countdown (+ "Paused"), `NotificationBell` (poll 30 s, dropdown, mark-all), ticket status buttons driven by the transition matrix constants

## Phase 5 — Frontend pages complete (~4 h)

- [ ] 5.1 Dashboard: `use-dashboard` hooks + `/dashboard` — KPI grid (3 light + brown `DarkKpiCard`), tickets-per-day bar chart, SLA trend area chart, breakdowns, recent tickets table — loading skeletons + per-widget error states
- [ ] 5.2 Ticket detail polish: right control panel (status buttons, SLA countdown rows, priority/category selects, assignee combobox, self-assign), comment timeline, audit timeline, empty/loading/404 states
- [ ] 5.3 Admin pages: `/admin/users` (table + modal + role/active mutations), `/admin/categories` (inline edit), `/admin/sla` (4 policy cards)
- [ ] 5.4 `/audit` page (filters synced to URL, old→new chips)
- [ ] 5.5 Role guards + tab nav visibility per role; requester redirect off `/dashboard`; responsive pass (rail collapse, TabNav sheet, table scroll, card stacking) + focus rings/aria labels sweep

## Phase 6 — Seed, deploy, verify (~3 h)

- [ ] 6.1 `app/db.seed` module: 1+3+5 users, 6 categories, 4 SLA policies, ~40 tickets across 45 days with comments/notes/audit/notifications; ≥3 breached, ≥3 at-risk, several paused; idempotent; demo credentials table in README verified
- [ ] 6.2 GitHub repo: push, enable Actions; create Neon DB + Render service + Vercel project per DEPLOYMENT §2–§4; add all secrets
- [ ] 6.3 Wire `ci.yml` + `deploy.yml` (DEPLOYMENT §5); push to `main`; watch migrate → Render → Vercel go green
- [ ] 6.4 Run seed against production DB; execute the full POST-DEPLOY SMOKE TEST (DEPLOYMENT §8) end-to-end in the browser
- [ ] 6.5 README: real live URLs, screenshots from production, badge links; demo credentials confirmed

## Phase 7 — Polish & demo (remaining time)

- [ ] 7.1 Empty/loading/error states sweep (every list, every form, cold-start "waking up" retry)
- [ ] 7.2 Mobile layout pass + accessibility spot check (labels, focus, contrast)
- [ ] 7.3 Performance sanity: no waterfall queries on dashboard (parallel), `placeholderData` on paginated lists
- [ ] 7.4 `docs/DEMO_SCRIPT.md` rehearsed end-to-end (timed ~4 min); all 16 docs re-read for consistency with the final code
- [ ] 7.5 Final `ruff`/`pytest`/`lint`/`typecheck`/`build` + commit hygiene (`docs: final consistency pass`)
- [ ] 7.6 **Stretch only if every box above is ticked:** CSV export (S4), dark mode (S5), Vitest component tests (TESTING §3)

## 8. Cut list (drop in this order when time runs out)

1. **Stretch features** (Phase 7.6) — all of them, by definition.
2. `/audit` global page → keep only per-ticket timelines (still satisfies "audit visible to admins" via ticket pages; note the cut in the README).
3. Dashboard extras: drop the SLA-trend chart and breakdowns → keep KPI cards + tickets-per-day + recent tickets.
4. `tab=` server presets → ship tabs as pure client-side presets of `assignee_id` filters.
5. Bell polling interval 60 s + no dropdown → unread badge only (count endpoint).
6. Inline note on status transitions (`note` field) → drop the prompt; comments cover it.
7. Password-change page → fold into `/settings` as the only card (profile becomes read-only text).
8. **Never cut:** auth+RBAC, ticket CRUD, state machine with pause/resume SLA math, assignment (manual + auto), comments with internal notes, audit trail, one deployable production environment, seed data that makes the dashboard alive.

## 9. Definition of done per phase

- All MVP boxes ticked; `docs/IMPLEMENTATION_PLAN.md` committed.
- Backend: `ruff check . && ruff format --check . && pytest -q` green.
- Frontend: `npm run lint && npm run typecheck && npm run build` green.
- CI green on GitHub; (from Phase 6) production smoke test passed.
- No behavior changed without the corresponding `/docs` file updated in the same session ([AGENTS.md rules](../AGENTS.md)).
