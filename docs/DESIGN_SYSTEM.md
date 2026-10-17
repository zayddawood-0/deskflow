# Design System — DeskFlow

Reference style: light, airy, rounded, orange as the single accent (the uploaded "InvestIQ" dashboard). Every color, radius and component below is normative — Tailwind classes may only use these tokens (`docs/DESIGN_SYSTEM.md` is the source; no ad-hoc hex values in components).

## 1. Color tokens

| Token | Hex | Usage |
|---|---|---|
| `bg-page` | `#EDEDED` | Outer page background (behind the app canvas) |
| `bg-canvas` | `#F5F5F5` | App canvas (main content area) |
| `surface` | `#FFFFFF` | Cards, tables, navbar, modals |
| `surface-muted` | `#EFEFEF` | Secondary card containers, input backgrounds, icon-button rest state |
| `accent` | `#F0510F` | Primary orange: CTA buttons, active chart bars, line charts, focus accents, "In progress" status |
| `accent-hover` | `#D9450A` | Hover/pressed state of accent elements |
| `accent-soft` | `#FDEBE3` | Soft orange tint: hover wash, badge backgrounds, chart gradient start |
| `brown` | `#3D2416` | Dark highlighted KPI card (SLA Breaches), brown chart variant (white text on it) |
| `beige` | `#E4DDD2` | Neutral/inactive chart bars, "older" data |
| `ink` | `#111111` | Primary text, dark nav pill background |
| `ink-muted` | `#7A7A7A` | Secondary text, subtitles, table headers |
| `line` | `#E6E6E6` | Borders, dividers, table row separators |
| `status-resolved` | `#22A06B` | Resolved pill / success |
| `status-pending` | `#E8A33D` | On hold pill / pending / warning |
| `status-open` | `#5B6B7F` | Open pill (blue-gray) |
| `status-progress` | `#F0510F` | In progress pill (= accent) |
| `status-closed` | `#9A9A9A` | Closed pill (gray) |
| `status-reopened` | `#7A5AF8` | Reopened pill (purple) |
| `negative` | `#E5481B` | Breached SLA, negative deltas |
| `positive` | `#F0510F` | Positive trend arrows (orange, per reference) — used with the arrow glyph, never as "green success" text |

Status ↔ color mapping is exported from `src/lib/constants.ts` as `STATUS_COLORS` and must match the backend enum values exactly.

### 1.1 CSS variables (`src/app/globals.css`)

```css
:root {
  --bg-page: #EDEDED;
  --bg-canvas: #F5F5F5;
  --surface: #FFFFFF;
  --surface-muted: #EFEFEF;
  --accent: #F0510F;
  --accent-hover: #D9450A;
  --accent-soft: #FDEBE3;
  --brown: #3D2416;
  --beige: #E4DDD2;
  --ink: #111111;
  --ink-muted: #7A7A7A;
  --line: #E6E6E6;
  --status-resolved: #22A06B;
  --status-pending: #E8A33D;
  --status-open: #5B6B7F;
  --status-progress: #F0510F;
  --status-closed: #9A9A9A;
  --status-reopened: #7A5AF8;
  --negative: #E5481B;

  --radius-card: 24px;
  --radius-control: 9999px;
}
```

### 1.2 Tailwind theme (`tailwind.config.ts`)

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: { DEFAULT: "#EDEDED", canvas: "#F5F5F5" },
        surface: { DEFAULT: "#FFFFFF", muted: "#EFEFEF" },
        accent: { DEFAULT: "#F0510F", hover: "#D9450A", soft: "#FDEBE3" },
        brown: "#3D2416",
        beige: "#E4DDD2",
        ink: { DEFAULT: "#111111", muted: "#7A7A7A" },
        line: "#E6E6E6",
        negative: "#E5481B",
        status: {
          resolved: "#22A06B",
          pending: "#E8A33D",
          open: "#5B6B7F",
          progress: "#F0510F",
          closed: "#9A9A9A",
          reopened: "#7A5AF8",
        },
      },
      borderRadius: {
        card: "24px",
        control: "9999px",
      },
      fontFamily: {
        sans: ["var(--font-manrope)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(17,17,17,0.04), 0 8px 24px rgba(17,17,17,0.04)",
        pop: "0 12px 40px rgba(17,17,17,0.12)",
        rail: "0 0 0 1px rgba(17,17,17,0.04)",
      },
    },
  },
  plugins: [],
};
export default config;
```

`Manrope` is loaded via `next/font/google` in `src/app/layout.tsx` and exposed as `--font-manrope`.

## 2. Typography

| Role | Spec |
|---|---|
| Font | **Manrope** 400/500/600/700/800 (geometric grotesk, per reference) |
| Page greeting | `text-4xl font-extrabold tracking-tight text-ink` — e.g. "Welcome back, Bruno!" |
| Page subtitle | `text-sm text-ink-muted` directly under the greeting ("Here's what's happening with your queue today.") |
| Section heading | `text-lg font-bold text-ink` |
| Card title | `text-base font-semibold text-ink` + tiny subtitle `text-xs text-ink-muted` ("Track your performance.") |
| KPI value | `text-3xl font-extrabold text-ink tabular-nums` (white on the brown card) |
| Table header | `text-xs font-medium uppercase tracking-wide text-ink-muted` |
| Body / list text | `text-sm text-ink` |
| Muted meta | `text-xs text-ink-muted` |
| Numbers everywhere | `font-variant-numeric: tabular-nums` (class `tabular-nums`) so countdowns don't jitter |

## 3. Spacing, radii, shadows, grid

- **Spacing:** default Tailwind scale; section gap `gap-6`, card padding `p-6`, page padding `px-6 py-8` (`px-4 py-6` on mobile).
- **Radii:** cards & big containers `rounded-card` (24px, ≈ `rounded-3xl`); inputs/selects `rounded-xl` (12px); **buttons, nav items, tabs, badges: `rounded-control` (pill)**; icon buttons: `rounded-full` at 40×40px; avatars `rounded-full`.
- **Shadows:** `shadow-card` for resting cards; `shadow-pop` for modals/dropdowns/sheet; never hard black shadows.
- **Layout:** navbar height 72px (sticky, `surface`, bottom border `line`); left icon rail 64px wide (fixed, `surface`, `rounded-card` card look on desktop); main content max-width 1440px; content grid `grid-cols-12` with `col-span-9` main + `col-span-3` side panel on the dashboard.
- **Responsive:** < 1024px → icon rail hidden, tab nav collapses into a sheet/drawer triggered by a menu icon button, KPI cards go 2-up; < 640px → 1-up cards, tables become stacked cards or horizontally scrollable.

## 4. Charts (Recharts)

| Chart | Spec |
|---|---|
| Tickets per day (bar) | Rounded-top bars (`radius={[6,6,0,0]}`), last 7 days `#F0510F`, older days `#E4DDD2`; grid `#E6E6E6` dashed 1 3, axis labels `text-xs #7A7A7A`, no Y-axis decimals |
| SLA compliance trend (line) | Smooth (`type="monotone"`, `tension 0.4`), stroke `#F0510F` 2.5px, `Area` fill: vertical gradient `#FDEBE3 → rgba(240,81,15,0)` |
| Brown variant (inside `DarkKpiCard` / highlighted panel) | Stroke `#F0510F` on `#3D2416` background, subtle fill `rgba(240,81,15,0.25)` |
| Breakdowns (priority/category) | Horizontal bar chart or donut; priority colors: CRITICAL `#E5481B`, HIGH `#F0510F`, MEDIUM `#E8A33D`, LOW `#E4DDD2`; category = monochrome orange steps `#F0510F → #FDEBE3` |
| Tooltip | `surface` card, `rounded-xl`, `shadow-pop`, `text-xs` |

## 5. Component specs (`src/components/ui/*`, `src/components/layout/*`)

### Button
Variants (cva): `primary` (bg `accent`, text white, hover `accent-hover`), `secondary` (bg `surface`, border `line`, text `ink`, hover `surface-muted`), `ghost` (transparent, hover `surface-muted`), `danger` (bg `negative`, white). Sizes: `sm` h-9 px-4, `md` h-10 px-5, `lg` h-12 px-6. Shape: **always pill** (`rounded-control`), `text-sm font-semibold`, `inline-flex items-center gap-2` (icon before label), focus ring `focus-visible:ring-2 ring-accent/40`, disabled `opacity-50`.
Primary CTA pattern: orange pill with a `+` lucide icon — "New ticket".

### IconButton
40×40 `rounded-full`, variants `surface` (bg `surface`, border `line`) and `muted` (bg `surface-muted`), icon `size-5 text-ink`, hover slightly darker, **required `aria-label`**, focus ring as Button. Used for bell, mail, search, rail icons.

### Card
`bg-surface rounded-card shadow-card p-6 border border-line/60`. Optional `title` + `subtitle` header row (title `font-semibold`, subtitle `text-xs text-ink-muted`), optional action slot on the right.

### KpiCard
Card with: tiny label (uppercase `text-xs text-ink-muted`), value `text-3xl font-extrabold tabular-nums`, trend row (`trending-up` lucide icon in `accent` + "+12% vs last week" `text-xs`), and optional mini chart slot. Used for Open, In progress, Resolved this week.

### DarkKpiCard
Same layout on `bg-brown text-white` (no border): label/value in white, trend icon in `accent`, background mini chart line in `accent`. Used for **SLA Breaches**.

### StatusPill
Pill (`rounded-control border px-3 py-1 text-xs font-medium`) with a 6px **colored dot + text**, colors from `STATUS_COLORS` (dot and text share the color, border is `color/30`, bg transparent/`color/5`). Labels: Open, In progress, On hold, Resolved, Closed, Reopened (sentence case).

### PriorityBadge
Outlined pill with dot: LOW `ink-muted`, MEDIUM `status-pending`, HIGH `accent`, CRITICAL `negative` (CRITICAL text may be bold).

### SlaBadge + countdown
Pill with dot + state text: ON_TRACK `status-resolved`, AT_RISK `status-pending`, BREACHED `negative`. Beside it, a countdown `text-sm font-semibold tabular-nums` formatted `2d 04:11:07` / `04:11:07` (negative time shown as `OVERDUE` in `negative`). If `paused_at != null` → renders "Paused" with a `pause` icon instead of a ticking timer. Countdown ticks every second client-side, anchored to `*_due_at` and the server's `Date`/render time; **the backend remains the source of truth for `sla_state`.**

### Avatar
`rounded-full` initials on a tinted background (deterministic hue from user id, always light/neutral — e.g. `bg-accent-soft text-accent`), sizes 32/40px; `full_name` as `title`.

### DataTable
Wrapper: `bg-surface rounded-card shadow-card overflow-hidden`. `<table>` with `text-sm`, header row `text-xs uppercase text-ink-muted` on `bg-surface`, rows `border-t border-line` with `hover:bg-page-canvas/50`, `py-3 px-4`. Cells combine Avatar+name, `#TCK-1042` in `font-semibold tabular-nums`, StatusPill, PriorityBadge, SlaBadge, relative date (`text-ink-muted`). Row click → ticket detail. Pagination footer: page size select + prev/next pill buttons + "x–y of N".

### TabNav
Center of navbar: pill container `bg-surface-muted rounded-control p-1` with tab pills; **active tab = white pill + a black circular icon chip** (`bg-ink text-white rounded-full size-6`) + `font-semibold` label; inactive = `text-ink-muted`. On < 1024px: renders a menu IconButton opening a `Sheet` with the same items.

### IconRail
Left 64px vertical column: circular icon buttons (search, share, calendar, star, shield — `layout` icons per the reference) stacked with 12px gaps, logout pinned to the bottom (`text-negative` hover). Active item: `bg-ink text-white` circle. Hidden below 1024px (replaced by entries in the TabNav sheet + navbar avatar menu).

### NotificationBell
IconButton containing `bell` + unread badge (absolute `-top-1 -right-1` dot, `bg-accent text-white text-[10px] min-w-4 h-4 rounded-full`) — number shown up to `9+`. Click opens a dropdown (`surface`, `rounded-card`, `shadow-pop`, max-h 420px scroll): items with icon per type, title, relative time, unread row marked with `bg-accent-soft`; footer "Mark all as read" (secondary button size sm). Polls `unread-count` every 30 s; list fetched on open.

### Modal / Sheet
Modal: centered, `bg-surface rounded-card shadow-pop p-6 w-full max-w-lg`, backdrop `bg-ink/40 backdrop-blur-sm`, `Dialog` from Radix with focus trap + `aria-labelledby`. Sheet: slide-in panel (`right` for filters/mobile nav, `left` optional), `w-full max-w-sm`, same surface treatment. Both closed by Esc/backdrop.

### EmptyState
Centered `py-16 text-center`: icon in a `bg-surface-muted rounded-full size-12` circle, `font-semibold text-ink` title, `text-sm text-ink-muted` description, optional primary button. Copy examples: "No tickets here yet", "Nothing matches those filters".

### Skeleton
Pulse blocks (`animate-pulse bg-surface-muted rounded-xl`) shaped like the real content (KPI card skeleton, table rows skeleton — 6 rows, ticket detail skeleton). Used for every loading state; no spinners except inside buttons.

### Toaster
`sonner` toast styling to match: `rounded-control`? → **toasts use `rounded-card` (16px min)**, white surface, `shadow-pop`, icon per kind (success `status-resolved`, error `negative`, info `accent`). Error toasts show `error.message` from the API envelope; 4000 ms default.

## 6. Accessibility rules

- All icon-only controls require `aria-label` (IconButton enforces it in TS: `label` prop → `aria-label`).
- Focus visible everywhere: `focus-visible:ring-2 ring-accent/40 ring-offset-2`.
- Contrast: `#111111` on white = 18.9:1; `#7A7A7A` on white = 4.6:1 (≥ AA for text); status pill text on tinted bg re-checked per color; white on `#F0510F` used only for ≥ 14px semibold (≈ 3.4:1 — acceptable for UI components, verified against reference).
- Live regions: countdown uses `aria-live="off"` (avoid SR spam); toasts are `role="status"`/`role="alert"` (sonner default).
- Tables use `<th scope="col">`; modals trap focus (Radix); mobile drawer closes on route change.

## 7. Page-level composition

- **Navbar** (all app pages): left = DeskFlow logo mark (orange rounded square with "D" + wordmark), center = TabNav (always: Dashboard¹, Tickets, Settings; admin adds: Users, Audit — tabs the role cannot use are not rendered²), right = mail IconButton, NotificationBell IconButton, Avatar with dropdown (role badge, Settings, Log out).
  ¹ Dashboard visible to `agent`/`admin` only — requesters get the Tickets tab as their landing tab.
  ² Route access itself is still enforced client-side (`AuthProvider` bootstrap + `RoleGuard`) + backend RBAC.
- **Greeting header** on dashboard/list pages: `Welcome back, {first_name}!` + muted subtitle.
- **Primary CTA:** "New ticket" primary Button, top-right of Tickets pages.
- **Secondary buttons:** "Filters" and "Export"(stretch) as white pills with icons.
