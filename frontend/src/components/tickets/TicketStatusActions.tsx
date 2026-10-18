"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { TICKET_STATUS_LABELS, TICKET_TRANSITIONS, type UserRole } from "@/lib/constants";
import { useTransitionTicket } from "@/hooks/use-tickets";
import type { Ticket, TicketStatus } from "@/types/api";
import { Button } from "@/components/ui/Button";

export function TicketStatusActions({
  ticket,
  role,
}: {
  ticket: Ticket;
  role: UserRole;
}) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useTransitionTicket(ticket.id);

  const rules = TICKET_TRANSITIONS[ticket.status].filter((rule) =>
    rule.roles.includes(role),
  );

  if (rules.length === 0) {
    return <p className="text-sm text-ink-muted">No actions available for your role.</p>;
  }

  const run = (status: TicketStatus) => {
    setError(null);
    mutation.mutate(
      { status, note: note.trim() ? note.trim() : undefined },
      {
        onSuccess: () => setNote(""),
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : "Could not update the ticket."),
      },
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <textarea
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Add an optional note for this status change…"
        maxLength={1000}
        className="min-h-20 w-full rounded-xl border border-line bg-surface-muted px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      />
      {error ? (
        <p className="text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {rules.map((rule) => (
          <Button
            key={rule.to}
            variant={rule.to === "CLOSED" || rule.to === "RESOLVED" ? "secondary" : "primary"}
            size="sm"
            loading={mutation.isPending && mutation.variables?.status === rule.to}
            onClick={() => run(rule.to)}
          >
            {TICKET_STATUS_LABELS[rule.to]}
          </Button>
        ))}
      </div>
    </div>
  );
}
