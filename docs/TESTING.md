# Testing — DeskFlow

| | |
|---|---|
| Backend | pytest + FastAPI `TestClient` (httpx) against a dedicated Postgres test database; ruff lint + format gate |
| Frontend | ESLint (`next lint`) + `tsc --noEmit` + production build as the MVP gate; a few Vitest component tests only if time remains |
| CI parity | CI runs exactly the commands in §1 — locally green ⇒ CI green |

## 1. Commands

```bash
# backend
cd backend
ruff check . && ruff format --check .
pytest -q --cov=app --cov-report=term-missing

# frontend
cd frontend
npm run lint && npm run typecheck && npm run build
```

- Test DB: `TEST_DATABASE_URL` must point at a disposable database **distinct from `DATABASE_URL`** (local: `deskflow_test` in docker-compose; CI: a `deskflow_test` database created on the Postgres 16 service container before pytest). `conftest.py` refuses to start if `TEST_DATABASE_URL` is unset or equals `DATABASE_URL` (the app's own DB), then runs `Base.metadata.create_all` per session and wraps each test in a rolled-back transaction — fast and isolated; the seed script is **not** used (tests build minimal fixtures via `tests/factories.py`).
- Coverage target: **≥ 80 % line coverage on `app/services/`** (`--cov=app/services`); overall `app/` ≥ 70 %. The coverage gate is advisory locally, but low-coverage PRs get new tests before merging.

## 2. Test cases — backend

### 2.1 `test_health.py`
- `test_health_returns_ok_and_db_up` → 200 `{status, database: "up", version}` on `GET /api/v1/health`.

### 2.2 `test_auth.py`
- `test_register_creates_requester_and_returns_user` — role always `requester`, no token in response.
- `test_register_duplicate_email_conflicts` → 409 `CONFLICT`.
- `test_register_weak_password_rejected` (missing digit/short) → 422 with field details.
- `test_login_success_returns_access_and_sets_refresh_cookie` — body has `expires_in == 1800` and **no** `refresh_token` field; `Set-Cookie` carries `refresh_token` with `HttpOnly`, `SameSite=Lax`, `Path=/api/v1/auth`.
- `test_login_wrong_password_generic_401` — message identical to unknown-email case (no enumeration).
- `test_login_inactive_user_rejected` → 401.
- `test_login_rate_limited_after_5_attempts` → 429 `RATE_LIMITED` on the 6th.
- `test_refresh_rotates_token_and_revokes_old` — call refresh with the cookie from login → new access token + rotated `Set-Cookie`; sending the **old** cookie value again → 401.
- `test_refresh_rejected_when_missing_or_revoked_or_expired` → 401 (no cookie at all, or revoked/expired value).
- `test_logout_revokes_refresh_token_and_clears_cookie` → 204 with expired `Set-Cookie`, then refresh with that value → 401; logout again → still 204 (idempotent).
- `test_change_password_requires_current_and_revokes_other_sessions`.
- `test_me_requires_valid_token` (missing / garbage / expired) → 401.

### 2.3 `test_rbac.py`
- `test_requester_cannot_list_users` / `create_user` / `update_user` / `delete_user` → 403 `FORBIDDEN`.
- `test_agent_cannot_access_admin_endpoints` (users, categories write, sla write, `/audit`, `/dashboard/*`) → 403.
- `test_requester_cannot_see_dashboard_endpoints` → 403.
- `test_requester_ticket_list_scoped_to_own` — requester B's ticket invisible in list; detail → 404 (not 403 — existence hidden).
- `test_requester_cannot_patch_priority` → 403; `test_requester_cannot_add_internal_note` → 403.
- `test_admin_can_do_every_agent_endpoint` (smoke over transitions/self-assign/comments).
- `test_admin_cannot_deactivate_self` / `demote_self` → 409.
- `test_inactive_user_token_rejected_after_deactivation` → 401 on next request.

### 2.4 `test_tickets.py` (CRUD + list)
- `test_create_ticket_sets_defaults_and_due_dates` — `OPEN`, `TCK-####` sequential, due dates = created + policy minutes, `sla_state` `ON_TRACK`.
- `test_create_ticket_validation_errors` (short title, short description, bad priority, unknown/inactive category) → 422/404/409.
- `test_create_ticket_writes_ticket_created_audit`.
- `test_list_filters_status_priority_category_assignee_q_sort` — one test per filter asserting exact sets.
- `test_list_sla_state_filter` — fabricate breached/at-risk tickets with due-date math; filter returns the right ones.
- `test_list_pagination_envelope` — page_size=10 over 25 rows → `pages == 3`, `total == 25`.
- `test_agent_tab_presets` — `tab=mine` / `unassigned` resolve to the right assignee filters.
- `test_patch_priority_changes_and_audits` (agent) / `test_patch_priority_forbidden_for_requester`.
- `test_requester_can_edit_title_only_while_open` — allowed on OPEN; 409 after IN_PROGRESS.
- `test_foreign_ticket_detail_404` for requester.

### 2.5 `test_transitions.py` (state machine exhaustively)
- `test_all_valid_transitions_per_role` — parametrized over the full T1–T9 matrix: agent/admin succeed where the table says ✓; requester succeeds only on own tickets for T6–T8.
- `test_invalid_pairs_rejected_409` — parametrized over every other (from, to) combination (incl. `OPEN→CLOSED`, `OPEN→RESOLVED`, `ON_HOLD→RESOLVED`, `REOPENED→CLOSED`, self-transitions) asserting code `INVALID_TRANSITION` and the allowed list in `details`.
- `test_role_denied_transition_403` — requester attempting T1/T5, etc.
- `test_reopen_from_closed_within_window_ok` (audit-timestamped 6 days ago) and `test_reopen_from_closed_outside_window_409` (8 days) → `REOPEN_WINDOW_EXPIRED`.
- `test_first_responded_at_set_once_by_agent_transition` — second transition does not overwrite.
- `test_requester_transition_does_not_set_first_response`.
- `test_on_hold_sets_paused_at_and_resume_shifts_due_dates` — exact second-level assertions (created 10:00, hold at +2 h, resume at +8 h → `total_paused_seconds == 21600`, both due dates `+6 h`).
- `test_status_change_writes_audit_and_notifications` (requester notified on RESOLVED; assignee on REOPENED/CLOSED).
- `test_transition_with_note_creates_comment`.

### 2.6 `test_sla.py`
- `test_compute_due_dates_per_priority` — all four policies.
- `test_sla_state_on_track_at_risk_breached` — parametrized clock positions (50 %, 75 %, 101 % of target).
- `test_sla_state_uses_worst_of_two_targets`.
- `test_paused_ticket_freezes_elapsed` — while `paused_at` set, moving `now` forward does not change the state.
- `test_resume_shifts_and_then_breach_math` — worked Example B from [WORKFLOWS §5.3](WORKFLOWS.md#5-sla-calculation-algorithm).
- `test_breach_persists_flag_audit_and_notifications_once` — second read does not duplicate audit/notifications.
- `test_at_risk_notification_deduped` — second trigger with the same (user, type, ticket) creates nothing, even after the first is marked read.
- `test_resolved_on_time_vs_late` — `resolved_at` compared against shifted `resolution_due_at`.
- `test_sla_scan_endpoint_scans_all_open_tickets` — `X-Internal-Token` correct → 200 with counts; wrong/missing → 403.
- `test_sla_scan_idempotent` — running the scan twice in a row: second response `newly_breached == 0`, notification/audit counts unchanged.

### 2.7 `test_assignment.py`
- `test_auto_assign_picks_least_loaded_agent` — agent A has 2 open, B has 1, C has 0 → C; `auto_assigned=True`, audit `AUTO_ASSIGNED` with `actor_id NULL`, requester + assignee notified.
- `test_auto_assign_disabled_flag_respected`.
- `test_auto_assign_leaves_unassigned_when_no_agents`.
- `test_auto_assign_ignores_inactive_agents`.
- `test_self_assign_unassigned_ok` — audit `ASSIGNED`, requester notified, self not notified.
- `test_self_assign_already_taken_409` / `already_mine_409 ALREADY_ASSIGNED`.
- `test_admin_assign_and_reassign_records_old_value` — audit old/new both present; notify new assignee + requester.
- `test_admin_assign_to_non_agent_422` / `to_inactive_user_422`.
- `test_unassign_clears_flag_and_notifies_requester`.

### 2.8 `test_comments.py`
- `test_agent_public_comment_sets_first_response_and_notifies_requester`.
- `test_internal_note_hidden_from_requester` — list endpoint for the requester excludes it; detail/serialization paths assert absence; the agent/admin list includes it.
- `test_requester_cannot_create_internal_note` → 403.
- `test_requester_comment_notifies_assignee`.
- `test_internal_note_does_not_set_first_response` and does not notify the requester.
- `test_comment_validation_empty_and_too_long` → 422.
- `test_comment_writes_audit` (`COMMENT_ADDED` / `INTERNAL_NOTE_ADDED`).

### 2.9 `test_audit.py`
- `test_audit_endpoint_admin_only` → 403 for requester/agent.
- `test_audit_filters_actor_action_entity_ticket_dates`.
- `test_audit_immutable_in_db` — raw SQL `UPDATE`/`DELETE` raises (trigger) inside a transaction that is rolled back.
- `test_ticket_timeline_endpoint_scoped`.
- `test_password_change_audit_has_no_values`.

### 2.10 `test_dashboard.py`
- `test_stats_values_match_fixtures` — construct a known universe; assert every number.
- `test_tickets_per_day_zero_fills_days` and respects `days` bounds.
- `test_sla_trend_compliance_math` — known resolved set → exact percentages; zero-resolution day → `null`.
- `test_breakdown_zero_fills_priorities`, excludes inactive work.
- `test_recent_tickets_order_and_sla_state`.
- `test_dashboard_requester_403`.

### 2.11 `test_notifications.py`
- `test_unread_count_and_list_scoping` (user A never sees B's rows).
- `test_mark_one_read` / `test_mark_all_read` / `test_foreign_notification_404`.
- `test_no_notification_for_inactive_recipients` and `no self-notification for actor`.

### 2.12 `test_categories_and_sla.py`
- `test_categories_readable_by_all_but_writable_by_admin_only` (requester/agent write attempts → 403).
- `test_category_duplicate_name_409` and `test_category_deactivate_keeps_ticket_fk`.
- `test_inactive_category_rejected_on_ticket_create` → 409.
- `test_sla_policies_readable_by_all_writable_by_admin_only`.
- `test_sla_policy_validation` (out of range, first > resolution → 422) and `test_sla_policy_update_audited`.
- `test_policy_change_affects_new_tickets_only` — old ticket keeps due dates, new ticket uses the new policy.

## 3. Test cases — frontend

MVP gate (runs in CI, no extra framework):

| Check | Command | Fails on |
|---|---|---|
| Lint | `npm run lint` | ESLint errors (incl. `no-explicit-any`), unused vars |
| Types | `npm run typecheck` (`next typegen && tsc --noEmit`) | any `any`, prop mismatches vs `types/api.ts` |
| Build | `npm run build` | Server component/client boundary violations, bad `next/font` usage, missing env at build |

Component tests (**stretch** — only if the schedule allows; Vitest + React Testing Library in `src/components/__tests__/`):
- `StatusPill` renders each of the 6 statuses with the right color class.
- `SlaBadge` shows "Paused" when `paused_at` is set, counts down otherwise.
- `TicketStatusButtons` renders only the transitions for (role, status) from the matrix.
- `CommentForm` hides the Public/Internal toggle for requesters.
- `NotificationBell` shows the `9+` cap.

## 4. What "tested" means for this project

- Every acceptance criterion marked `AC` in the [PRD](PRD.md) maps to at least one test above (traceability is by name: `US-R4 ↔ test_reopen_*`, `US-G5 ↔ test_comments`, `US-B6 ↔ test_dashboard`, …).
- A behavior change is not done until the corresponding test is updated in the same commit ([AGENTS.md definition of done](../AGENTS.md)).
- Manual QA still required for the visual layer: the checklist in [DEPLOYMENT §8](DEPLOYMENT.md#8-post-deploy-smoke-test) doubles as the UI regression pass.
