"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import type { UserRole } from "@/lib/constants";
import { useAgents } from "@/hooks/use-users";
import { useAssignTicket, useSelfAssign, useUnassignTicket } from "@/hooks/use-tickets";
import type { Ticket } from "@/types/api";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";

export function AssignControl({ ticket, role }: { ticket: Ticket; role: UserRole }) {
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(ticket.assignee?.id ?? "");
  const agents = useAgents();
  const assign = useAssignTicket(ticket.id);
  const unassign = useUnassignTicket(ticket.id);
  const selfAssign = useSelfAssign(ticket.id);

  const handleError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Assignment failed.");
  };

  if (role === "requester") {
    return null;
  }

  if (role === "agent") {
    if (ticket.assignee) {
      return null;
    }
    return (
      <Button
        variant="secondary"
        size="sm"
        loading={selfAssign.isPending}
        onClick={() =>
          selfAssign.mutate(undefined, { onError: handleError })
        }
      >
        Assign to me
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Select
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          aria-label="Assignee"
        >
          <option value="">Unassigned</option>
          {(agents.data ?? []).map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.full_name}
            </option>
          ))}
        </Select>
        <Button
          size="sm"
          loading={assign.isPending}
          disabled={!selected || selected === ticket.assignee?.id}
          onClick={() =>
            assign.mutate({ assignee_id: selected }, { onError: handleError })
          }
        >
          Assign
        </Button>
        {ticket.assignee ? (
          <Button
            variant="ghost"
            size="sm"
            loading={unassign.isPending}
            onClick={() => unassign.mutate(undefined, { onError: handleError })}
          >
            Unassign
          </Button>
        ) : null}
      </div>
      {error ? (
        <p className="text-xs text-negative" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
