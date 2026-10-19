"use client";

import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { ROLE_LABELS, TICKET_STATUS_LABELS } from "@/lib/constants";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useTicketComments } from "@/hooks/use-comments";
import { useTicket, useTicketAudit } from "@/hooks/use-tickets";
import type { AuditEntry } from "@/types/api";
import { Card } from "@/components/ui/Card";
import { PriorityPill } from "@/components/ui/PriorityPill";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { AssignControl } from "@/components/tickets/AssignControl";
import { CommentForm } from "@/components/tickets/CommentForm";
import { CommentList } from "@/components/tickets/CommentList";
import { SlaBadge } from "@/components/tickets/SlaBadge";
import { TicketStatusActions } from "@/components/tickets/TicketStatusActions";

function actionLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string" && value.length === 36 && value.includes("-")) {
    return value.slice(0, 8);
  }
  return String(value);
}

function AuditEntryRow({ entry }: { entry: AuditEntry }) {
  return (
    <li className="flex flex-col gap-1 border-b border-line/70 py-3 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-ink">{actionLabel(entry.action)}</span>
        <span className="text-xs text-ink-muted">{formatDate(entry.created_at)}</span>
      </div>
      <span className="text-xs text-ink-muted">
        {entry.actor ? `${entry.actor.full_name} · ${ROLE_LABELS[entry.actor.role]}` : "System"}
      </span>
      {entry.old_value || entry.new_value ? (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {entry.old_value
            ? Object.entries(entry.old_value).map(([key, value]) => (
                <span
                  key={`old-${key}`}
                  className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] text-ink-muted"
                >
                  {key}: {renderValue(value)}
                </span>
              ))
            : null}
          {entry.new_value
            ? Object.entries(entry.new_value).map(([key, value]) => (
                <span
                  key={`new-${key}`}
                  className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent"
                >
                  {key}: {renderValue(value)}
                </span>
              ))
            : null}
        </div>
      ) : null}
    </li>
  );
}

export default function TicketDetailPage() {
  const { user } = useAuth();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const ticket = useTicket(id);
  const audit = useTicketAudit(id);
  const comments = useTicketComments(id);

  if (ticket.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (ticket.isError || !ticket.data) {
    const message =
      ticket.error instanceof ApiError ? ticket.error.message : "Ticket not found.";
    return (
      <Card title="Ticket unavailable">
        <p className="text-sm text-ink-muted">{message}</p>
      </Card>
    );
  }

  const data = ticket.data;
  const role = user?.role ?? "requester";
  const canPostInternal = role === "agent" || role === "admin";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
          {data.ticket_number}
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink">{data.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusPill status={data.status} />
          <PriorityPill priority={data.priority} />
          <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-ink-muted">
            {data.category.name}
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex flex-col gap-6">
          <Card title="Description">
            <p className="whitespace-pre-wrap text-sm text-ink">{data.description}</p>
          </Card>

          <Card title="Conversation" subtitle="Public comments and internal notes">
            {comments.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <CommentList comments={comments.data?.items ?? []} />
            )}
            <div className="mt-4 border-t border-line/70 pt-4">
              <CommentForm ticketId={id} canPostInternal={canPostInternal} />
            </div>
          </Card>

          <Card title="Activity" subtitle="Audit trail for this ticket">
            {audit.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : audit.data && audit.data.items.length > 0 ? (
              <ul>
                {audit.data.items.map((entry) => (
                  <AuditEntryRow key={entry.id} entry={entry} />
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-muted">No activity yet.</p>
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card title="SLA">
            <dl className="flex flex-col gap-3 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">State</dt>
                <dd>
                  <SlaBadge state={data.sla_state} />
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">First response due</dt>
                <dd className="font-medium text-ink">
                  {formatDate(data.first_response_due_at)}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Resolution due</dt>
                <dd className="font-medium text-ink">{formatDate(data.resolution_due_at)}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">
                  {data.paused_at ? "Paused since" : "Last update"}
                </dt>
                <dd className="font-medium text-ink">
                  {data.paused_at
                    ? formatDate(data.paused_at)
                    : formatDate(data.updated_at)}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="People">
            <dl className="flex flex-col gap-3 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Requester</dt>
                <dd className="font-medium text-ink">{data.requester.full_name}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Assignee</dt>
                <dd className="font-medium text-ink">
                  {data.assignee?.full_name ?? "Unassigned"}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Current status</dt>
                <dd className="font-medium text-ink">{TICKET_STATUS_LABELS[data.status]}</dd>
              </div>
            </dl>
          </Card>

          <Card title="Actions">
            <div className="flex flex-col gap-4">
              <TicketStatusActions ticket={data} role={role} />
              <AssignControl ticket={data} role={role} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
