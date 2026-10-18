import Link from "next/link";
import type { Ticket } from "@/types/api";
import { PriorityPill } from "@/components/ui/PriorityPill";
import { StatusPill } from "@/components/ui/StatusPill";
import { SlaBadge } from "@/components/tickets/SlaBadge";

export function TicketTable({ tickets }: { tickets: Ticket[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-muted">
            <th className="py-3 pr-4 font-medium">Ticket</th>
            <th className="py-3 pr-4 font-medium">Status</th>
            <th className="py-3 pr-4 font-medium">Priority</th>
            <th className="py-3 pr-4 font-medium">SLA</th>
            <th className="py-3 pr-4 font-medium">Assignee</th>
            <th className="py-3 pr-4 font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr
              key={ticket.id}
              className="border-b border-line/70 transition-colors last:border-b-0 hover:bg-surface-muted/60"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/tickets/${ticket.id}`}
                  className="flex flex-col gap-0.5 focus-visible:outline-none"
                >
                  <span className="text-xs font-medium text-ink-muted">
                    {ticket.ticket_number}
                  </span>
                  <span className="font-semibold text-ink hover:text-accent">
                    {ticket.title}
                  </span>
                  <span className="text-xs text-ink-muted">{ticket.category.name}</span>
                </Link>
              </td>
              <td className="py-3 pr-4">
                <StatusPill status={ticket.status} />
              </td>
              <td className="py-3 pr-4">
                <PriorityPill priority={ticket.priority} />
              </td>
              <td className="py-3 pr-4">
                <SlaBadge state={ticket.sla_state} />
              </td>
              <td className="py-3 pr-4 text-ink">
                {ticket.assignee?.full_name ?? <span className="text-ink-muted">Unassigned</span>}
              </td>
              <td className="py-3 pr-4 text-ink-muted">{ticket.created_at.slice(0, 10)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
