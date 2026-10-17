# Frontend Spec — DeskFlow

| | |
|---|---|
| Framework | Next.js (App Router) + TypeScript strict, Tailwind, components per [DESIGN_SYSTEM](DESIGN_SYSTEM.md) |
| Data | TanStack Query via `src/hooks/*`; HTTP only through `src/lib/api-client.ts`; all calls **same-origin** `/api/v1/*` (Next `rewrites()` proxy → `BACKEND_URL`) |
| Forms | React Hook Form + Zod (`src/schemas/*`) |
| Auth | Access token in memory; refresh token in an httpOnly cookie owned by the backend (`Path=/api/v1/auth`) — see [AUTH_AND_SECURITY §3](AUTH_AND_SECURITY.md#3-token-storage-frontend) |

## 1. Sitemap & role access

| Route | requester | agent | admin | Notes |
|---|---|---|---|---|
| `/login` | ✓ | ✓ | ✓ | Public; redirects authed users → their landing page |
| `/register` | ✓ | ✓ | ✓ | Public; always creates `requester` |
| `/` | → `/tickets` | → `/dashboard` | → `/dashboard` | Root redirect by role |
| `/dashboard` | → `/tickets` | ✓ | ✓ | KPIs + charts |
| `/tickets` | ✓ (own) | ✓ | ✓ | List, filters, tabs |
| `/tickets/new` | ✓ | ✓ | ✓ | Create form |
| `/tickets/[id]` | ✓ (own) | ✓ | ✓ | Detail, SLA, comments, timeline |
| `/admin/users` | ✗ → `/tickets` | ✗ → `/tickets` | ✓ | User management |
| `/admin/categories` | ✗ | ✗ | ✓ | Category management |
| `/admin/sla` | ✗ | ✗ | ✓ | SLA policy editor |
| `/audit` | ✗ | ✗ | ✓ | Global audit log |
| `/settings` | ✓ | ✓ | ✓ | Profile + change password |

Enforcement: route protection is **client-side** — `AuthProvider` performs one silent `POST /api/v1/auth/refresh` on mount (the path-scoped httpOnly cookie rides along automatically); unauthenticated users are redirected to `/login` once it resolves, and `RoleGuard` hides/redirects wrong-role routes. The backend RBAC is the only real security boundary. (`middleware.ts` is intentionally not used for auth: the refresh cookie's `Path=/api/v1/auth` means page requests never carry it.)

## 2. Folder structure

```
frontend/
├── .env.example                    # BACKEND_URL, NEXT_PUBLIC_APP_NAME
├── next.config.ts                  # rewrites(): /api/:path* → ${BACKEND_URL}/api/:path*
├── tailwind.config.ts              # tokens from DESIGN_SYSTEM §1.2
├── tsconfig.json                   # strict: true
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Manrope via next/font, Toaster, AuthProvider, QueryProvider
│   │   ├── globals.css             # CSS variables (DESIGN_SYSTEM §1.1)
│   │   ├── page.tsx                # root redirect
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   └── (app)/
│   │       ├── layout.tsx          # Navbar + IconRail + auth guard (client)
│   │       ├── dashboard/page.tsx
│   │       ├── tickets/page.tsx
│   │       ├── tickets/new/page.tsx
│   │       ├── tickets/[id]/page.tsx
│   │       ├── admin/users/page.tsx
│   │       ├── admin/categories/page.tsx
│   │       ├── admin/sla/page.tsx
│   │       ├── audit/page.tsx
│   │       └── settings/page.tsx
│   ├── components/
│   │   ├── ui/                     # Button, IconButton, Card, KpiCard, DarkKpiCard, StatusPill,
│   │   │                           # PriorityBadge, SlaBadge, Avatar, DataTable, EmptyState,
│   │   │                           # Skeleton, Modal, Sheet, Select, Textarea, Input, Badge
│   │   ├── layout/                 # Navbar, IconRail, TabNav, NotificationBell, PageHeader
│   │   ├── tickets/                # TicketFilters, TicketTable, TicketStatusButtons,
│   │   │                           # AssigneeCombobox, CommentList, CommentForm, TicketTimeline
│   │   ├── dashboard/              # KpiGrid, TicketsPerDayChart, SlaTrendChart,
│   │   │                           # BreakdownCharts, RecentTicketsTable
│   │   └── admin/                  # UserTable, UserModal, CategoryTable, SlaPolicyCard
│   ├── hooks/
│   │   ├── use-auth.ts             # AuthProvider context + useAuth()
│   │   ├── use-tickets.ts          # list/detail/create/update + status/self-assign/assign
│   │   ├── use-comments.ts
│   │   ├── use-notifications.ts
│   │   ├── use-dashboard.ts
│   │   ├── use-users.ts
│   │   ├── use-categories.ts
│   │   ├── use-sla-policies.ts
│   │   └── use-audit.ts
│   ├── lib/
│   │   ├── api-client.ts           # fetch wrapper: base URL, Bearer, refresh-on-401, ApiError
│   │   ├── auth.ts                 # in-memory access-token store (single source for api-client)
│   │   ├── constants.ts            # STATUSES, PRIORITIES, ROLES, SLA_STATES, STATUS_COLORS…
│   │   ├── utils.ts                # cn(), formatDate, formatRelative, formatCountdown
│   │   └── guards.tsx              # RoleGuard component
│   ├── schemas/                    # Zod: auth.ts, ticket.ts, comment.ts, admin.ts
│   └── types/
│       └── api.ts                  # TS types mirroring API_SPEC §2.3 + response envelopes
```

## 3. API client & hooks pattern

### `lib/api-client.ts` (the only `fetch` call site)

```ts
// contract (see API_SPEC)
export class ApiError extends Error {
  constructor(public code: string, message: string,
              public status: number, public details?: { field: string; issue: string }[]) { super(message); }
}
export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T>
// - base = "/api/v1"  (same-origin; next.config.ts rewrites proxy to ${BACKEND_URL})
// - attaches Authorization from in-memory access token when present
// - cookies ride along automatically (same-origin) — the httpOnly refresh cookie is
//   only ever sent to /api/v1/auth/* (Path-scoped by the backend); JS never reads it
// - init.json → JSON.stringify + Content-Type header
// - !res.ok → parse {"error":{code,message,details}} → throw ApiError
// - on 401 code UNAUTHORIZED once: POST /api/v1/auth/refresh (empty body, cookie auth),
//   store new access token, retry original request once (single-flight across concurrent 401s)
// - after failed refresh: clear in-memory token, dispatch auth:logout event → AuthProvider redirects /login
```

### Hook pattern (every server interaction)

```ts
// src/hooks/use-tickets.ts
export function useTickets(params: TicketListParams) {
  return useQuery({
    queryKey: ["tickets", params],
    queryFn: () => api<Page<Ticket>>(`/tickets?${toQuery(params)}`),
    staleTime: 30_000,
    placeholderData: keepPreviousData,   // keeps pagination snappy
  });
}
export function useTransitionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, note }: TransitionInput) =>
      api<Ticket>(`/tickets/${id}/status`, { method: "POST", json: { status, note } }),
    onSuccess: (ticket) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["ticket", ticket.id] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
```

Rules: components never import `api-client` directly — always a hook; every mutation invalidates its affected keys (`tickets`, `ticket:<id>`, `dashboard`, `notifications`, `audit`); query keys are factored as shown so filters participate in the cache key.

## 4. Pages

### 4.1 `/login` — `(auth)` · public

- **Purpose:** email + password sign-in.
- **Layout:** centered Card (max-w-sm) on `bg-page` with logo, "Welcome back" heading, email + password `Input`s, primary "Sign in" button, link to `/register`. No navbar.
- **Fetches:** `POST /auth/login` (mutation, no query).
- **States:** idle → submitting (button spinner + disabled) → error toast (`error.message`; 429 → "Too many attempts…") → success redirect to landing page (`/dashboard` for agent/admin, `/tickets` for requester).
- **Interactions:** Zod validation on blur/submit; caps-lock hint optional.

### 4.2 `/register` — `(auth)` · public

- **Layout:** same centered card: full name, email, password, confirm password; "Create account" primary; link to `/login`; note "Accounts are created as employees — an admin can upgrade your role."
- **Fetches:** `POST /auth/register`.
- **States:** 409 (email taken) → field error on email; 422 → per-field errors from `details`; success → toast "Account created — sign in" → `/login`.

### 4.3 `/dashboard` — `(app)` · agent, admin

- **Purpose:** 5-second overview of IT support state.
- **Layout:** `PageHeader` ("Welcome back, {name}!") → KpiGrid: 4 cards in a row — `KpiCard` Open, `KpiCard` In progress, `KpiCard` Resolved this week, **`DarkKpiCard` SLA Breaches** (brown, with the wavy orange line mini-chart) → row: TicketsPerDayChart (col-span-8, bar) + BreakdownCharts (col-span-4, priority + category) → row: SlaTrendChart (col-span-8, orange area line) + side panel RecentTicketsTable? → full-width **RecentTicketsTable** (8 rows, status pills, SlaBadge).
- **Fetches (parallel):** `/dashboard/stats`, `/dashboard/tickets-per-day?days=30`, `/dashboard/sla-trend?days=30`, `/dashboard/breakdown`, `/dashboard/recent-tickets?limit=8`.
- **States:** per-widget skeletons (`animate-pulse` cards/rows); error → inline Card "Couldn't load the dashboard" + Retry button (toaster only for unexpected failures); Render cold start → the api-client surfaces a timeout error, page shows "Waking up the server… retrying" and auto-retries once after 5 s.
- **Interactions:** clicking a KPI card navigates to `/tickets?status=…` (or `?sla_state=BREACHED`); clicking a recent row opens the ticket; breakdown segments link to `/tickets?priority=…` / `?category_id=…`.
- **Requester hitting this route:** redirected to `/tickets` by `RoleGuard` (once `AuthProvider.user` resolves).

### 4.4 `/tickets` — `(app)` · all roles

- **Purpose:** the queue.
- **Layout:** `PageHeader` ("Tickets" + muted count subtitle) with right-aligned primary `Button` "New ticket" (+ icon) and secondary "Filters" toggle → `TabNav`-style preset pills for agents/admins: **My tickets · Unassigned · All** (requester: no tabs) → filter bar (Status multi-select, Priority select, Category select, SLA state select, search Input with debounce 300 ms, sort select) → `TicketTable` inside `DataTable` → pagination footer.
- **Row content:** `#TCK-1042` + title, requester Avatar+name (or assignee for agent view), StatusPill, PriorityBadge, SlaBadge + compact countdown, relative `updated_at`.
- **Fetches:** `GET /tickets` with `{tab?, status?, priority?, category_id?, assignee_id?, sla_state?, q?, sort, page, page_size}`; `/categories` for the filter select (cached).
- **States:** skeleton rows ×6 while loading; `EmptyState` "No tickets here yet" (no data) vs "Nothing matches those filters" (filters active) with a "Clear filters" ghost button; error → retry.
- **Interactions:** every filter writes to the URL query string (shareable, back-button safe); row click → `/tickets/[id]`; tabs are preset mutations of `assignee_id`/`tab` params.

### 4.5 `/tickets/new` — `(app)` · all roles

- **Purpose:** raise a ticket.
- **Layout:** single column Card (max-w-2xl): title Input, description Textarea (min-h 160), Category Select (active only), Priority Select (default MEDIUM, with the SLA targets shown as helper text per choice: "4h response / 24h resolution"), "Auto-assign to the least busy agent" Switch (default on), footer: primary "Create ticket" + ghost "Cancel".
- **Fetches:** `GET /categories`, `GET /sla-policies` (helper text); mutation `POST /tickets`.
- **States:** submitting disables form; 422 → field errors from `details` mapped onto RHF; success → `router.push(/tickets/{id})` + toast "Ticket TCK-1042 created".
- **Interactions:** live character counters (title 5–200, description ≥ 10); unsaved-changes guard via beforeunload optional.

### 4.6 `/tickets/[id]` — `(app)` · all (permission-filtered)

- **Purpose:** the full ticket conversation + controls.
- **Layout (two columns ≥1024px):**
  - **Left (col-span-8):** header: `#TCK-1042` + title, StatusPill, requester/assignee Avatars row → description Card → **CommentList** (public comments + internal notes; notes rendered with a `bg-accent-soft` left border and an "Internal note" chip, only for agents/admins) → CommentForm (Textarea + Public/Internal segmented toggle for agents/admins; requesters get a plain public box) → **TicketTimeline** (vertical audit entries: icon per action, actor, human sentence, old→new chips, timestamp).
  - **Right (col-span-4):** control panel Card — Status + **TicketStatusButtons** (only the transitions allowed for the current role/status, from WORKFLOWS §3; primary next action highlighted orange), **SlaBadge + full countdown** (First response / Resolution rows, "Paused" state with resume info), priority select (agent/admin), category select (agent/admin), **AssigneeCombobox** (admin) + "Self-assign" button (agent, unassigned only).
- **Fetches:** `GET /tickets/{id}`, `GET /tickets/{id}/comments`, `GET /tickets/{id}/audit`, `/categories`, `/sla-policies`, `/users` (admin, assignee combobox).
- **States:** detail skeleton; 404 → "Ticket not found" EmptyState (also for foreign requester tickets); status buttons render the allowed set — if none, show the terminal message ("Closed tickets can be reopened within 7 days").
- **Interactions:** each status button calls `useTransitionStatus` with an optional note prompt (Modal with textarea, skip for CLOSE?); comment submit appends optimistically; reopen button disabled with tooltip "Reopen window expired (7 days)" when applicable.

### 4.7 `/admin/users` — `(app)` · admin

- **Layout:** PageHeader + primary "New user" → `UserTable` (Avatar+name+email, role Select inline, active Switch, last column: deactivate IconButton) inside `DataTable`.
- **Fetches:** `GET /users?role=&is_active=&q=&page=`; mutations: `POST /users` (UserModal: name, email, password, role), `PATCH /users/{id}` (role/is_active/name), `DELETE /users/{id}`.
- **States:** skeletons; empty "No users match"; self-demotion/deactivate blocked client-side too (row actions disabled for the current user with tooltip) and surfaced from `409` if attempted.
- **Interactions:** confirm Modal before deactivating ("Their sessions will be revoked; history is kept."); success/failure toasts.

### 4.8 `/admin/categories` — `(app)` · admin

- **Layout:** PageHeader + "New category" → Card with a simple table: name (inline edit), description (inline edit), active Switch, created date.
- **Fetches:** `GET /categories?include_inactive=true`; mutations `POST/PATCH/DELETE /categories`.
- **States:** duplicate-name 409 → toast + revert inline edit; deleting a category in use → it just deactivates (no FK break) with helper text in the confirm modal.

### 4.9 `/admin/sla` — `(app)` · admin

- **Layout:** PageHeader ("SLA policies") + muted note "Applies to new tickets only." → grid of 4 `SlaPolicyCard`s (one per priority, priority-colored top border): two numeric `Input`s (first response minutes / resolution minutes) with hour helper text ("240 min = 4 h"), primary "Save" per card.
- **Fetches:** `GET /sla-policies`; `PUT /sla-policies/{priority}` per card.
- **States:** 422 (first > resolution or out of range) → field errors + toast; success → invalidates `/sla-policies` + toast "HIGH policy updated".

### 4.10 `/audit` — `(app)` · admin

- **Layout:** PageHeader ("Audit log") → filter row (actor Select from `/users`, action Select from constants, entity type Select, date range Inputs, ticket id Input) → `DataTable` (timestamp, actor Avatar, action Badge, entity, old→new value chips (JSON rendered as `key: old → new` chips), expandable row detail).
- **Fetches:** `GET /audit?actor_id=&action=&entity_type=&ticket_id=&date_from=&date_to=&page=`.
- **States:** skeletons; empty "No entries match"; values never contain passwords by design.
- **Interactions:** filters sync to URL; "View ticket" quick link when `ticket_id` present.

### 4.11 `/settings` — `(app)` · all roles

- **Layout:** two Cards side by side — "Profile" (Avatar, full name read-only email/role/joined date) and "Change password" (current, new, confirm + policy hint text).
- **Fetches:** `GET /auth/me`; `POST /auth/change-password`.
- **States:** wrong current password → 401 field error; success → toast "Password updated — other sessions signed out", form reset.

## 5. Shared behaviors

| Concern | Behavior |
|---|---|
| Auth bootstrap | `AuthProvider` on mount: `POST /api/v1/auth/refresh` (empty body; browser attaches the httpOnly cookie) to hydrate the access token + user (silent); loading → full-page skeleton; failure → treat as logged out; login sets the cookie via `Set-Cookie` (JS never touches it); logout = `POST /api/v1/auth/logout` + clear memory |
| Route protection | Client-side only: while `AuthProvider.user` is unknown, protected pages render a skeleton; unauthenticated → `/login`; wrong role → `RoleGuard` redirects to `/tickets`. Backend re-checks everything |
| Polling | `unread-count` every 30 s (paused when tab hidden via `enabled: !document.hidden` + visibility listener); no other polling in MVP |
| Dates | All rendering via `formatDate` (UTC-safe, e.g. "Oct 17, 09:23") and `formatRelative` ("2 h ago"); server data untouched |
| Errors | `ApiError.code` → toast message map in `lib/utils.ts`; field errors → RHF `setError`; 401 post-refresh → redirect |
| Loading | Skeletons (never spinners on first paint); buttons show inline spinner when pending |
| Responsive | Rail < 1024px hidden; TabNav → Sheet; tables horizontally scroll inside their Card; KPI grid 4→2→1 |
