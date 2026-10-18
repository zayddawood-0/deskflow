import { TICKET_STATUS_LABELS, type TicketStatus } from "@/lib/constants";
import { cn } from "@/lib/utils";

const STYLES: Record<TicketStatus, string> = {
  OPEN: "bg-status-open/10 text-status-open",
  IN_PROGRESS: "bg-status-progress/10 text-status-progress",
  ON_HOLD: "bg-status-pending/15 text-status-pending",
  RESOLVED: "bg-status-resolved/10 text-status-resolved",
  CLOSED: "bg-status-closed/10 text-status-closed",
  REOPENED: "bg-status-reopened/10 text-status-reopened",
};

export function StatusPill({
  status,
  className,
}: {
  status: TicketStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-control px-2.5 py-1 text-xs font-semibold",
        STYLES[status],
        className,
      )}
    >
      {TICKET_STATUS_LABELS[status]}
    </span>
  );
}
