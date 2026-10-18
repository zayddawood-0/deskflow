"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus, RotateCcw, Search } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useTickets } from "@/hooks/use-tickets";
import {
  DEFAULT_PAGE_SIZE,
  PRIORITY_LABELS,
  TICKET_PRIORITIES,
  TICKET_SORTS,
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TICKET_TABS,
  type TicketPriority,
  type TicketStatus,
  type UserRole,
} from "@/lib/constants";
import type { TicketListParams } from "@/types/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { TicketTable } from "@/components/tickets/TicketTable";

function TicketsContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const role: UserRole = user?.role ?? "requester";
  const tab = searchParams.get("tab") ?? "all";
  const status = searchParams.get("status") ?? "all";
  const priority = searchParams.get("priority") ?? "all";
  const sort = searchParams.get("sort") ?? "-created_at";
  const q = searchParams.get("q") ?? "";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const [search, setSearch] = useState(q);

  const params = useMemo<TicketListParams>(
    () => ({
      tab,
      status,
      priority,
      sort,
      q: q || undefined,
      page,
      page_size: DEFAULT_PAGE_SIZE,
    }),
    [tab, status, priority, sort, q, page],
  );

  const { data, isLoading, isError, error } = useTickets(params);

  const setParams = useCallback(
    (updates: Record<string, string | undefined>, resetPage = true) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (!value || value === "all") {
          next.delete(key);
        } else {
          next.set(key, value);
        }
      }
      if (resetPage) {
        next.delete("page");
      }
      const qs = next.toString();
      router.replace(qs ? `/tickets?${qs}` : "/tickets");
    },
    [router, searchParams],
  );

  const visibleTabs = TICKET_TABS.filter(
    (item) => !item.roles || item.roles.includes(role),
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-ink">Tickets</h1>
          <p className="text-sm text-ink-muted">
            {data ? `${data.total} ticket${data.total === 1 ? "" : "s"}` : "Loading your queue…"}
          </p>
        </div>
        <Link href="/tickets/new">
          <Button>
            <Plus className="size-4" aria-hidden />
            New ticket
          </Button>
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {visibleTabs.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setParams({ tab: item.value === "all" ? undefined : item.value })}
            className={
              tab === item.value
                ? "rounded-full bg-ink px-4 py-1.5 text-sm font-semibold text-white"
                : "rounded-full border border-line bg-surface px-4 py-1.5 text-sm font-medium text-ink hover:bg-surface-muted"
            }
          >
            {item.label}
          </button>
        ))}
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <form
            className="flex min-w-56 flex-1 items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              setParams({ q: search.trim() || undefined });
            }}
          >
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search tickets…"
              aria-label="Search tickets"
            />
            <Button type="submit" variant="secondary" size="sm">
              <Search className="size-4" aria-hidden />
            </Button>
          </form>

          <Select
            value={status}
            onChange={(event) => setParams({ status: event.target.value })}
            aria-label="Filter by status"
            className="w-40"
          >
            <option value="all">All statuses</option>
            {TICKET_STATUSES.map((value: TicketStatus) => (
              <option key={value} value={value}>
                {TICKET_STATUS_LABELS[value]}
              </option>
            ))}
          </Select>

          <Select
            value={priority}
            onChange={(event) => setParams({ priority: event.target.value })}
            aria-label="Filter by priority"
            className="w-40"
          >
            <option value="all">All priorities</option>
            {TICKET_PRIORITIES.map((value: TicketPriority) => (
              <option key={value} value={value}>
                {PRIORITY_LABELS[value]}
              </option>
            ))}
          </Select>

          <Select
            value={sort}
            onChange={(event) => setParams({ sort: event.target.value })}
            aria-label="Sort tickets"
            className="w-44"
          >
            {TICKET_SORTS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setSearch("");
              setParams({ tab: undefined, status: undefined, priority: undefined, q: undefined });
            }}
          >
            <RotateCcw className="size-4" aria-hidden />
            Reset
          </Button>
        </div>
      </Card>

      <Card className="p-4">
        {isLoading ? (
          <div className="flex flex-col gap-3 p-2">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        ) : isError ? (
          <p className="p-4 text-sm text-negative" role="alert">
            {error instanceof Error ? error.message : "Failed to load tickets."}
          </p>
        ) : data && data.items.length > 0 ? (
          <TicketTable tickets={data.items} />
        ) : (
          <p className="p-6 text-center text-sm text-ink-muted">No tickets match these filters.</p>
        )}
      </Card>

      {data && data.pages > 1 ? (
        <div className="flex items-center justify-between text-sm">
          <span className="text-ink-muted">
            Page {data.page} of {data.pages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={data.page <= 1}
              onClick={() => setParams({ page: String(data.page - 1) }, false)}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={data.page >= data.pages}
              onClick={() => setParams({ page: String(data.page + 1) }, false)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function TicketsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <TicketsContent />
    </Suspense>
  );
}
