import { PRIORITY_LABELS, type TicketPriority } from "@/lib/constants";
import { cn } from "@/lib/utils";

const STYLES: Record<TicketPriority, string> = {
  LOW: "bg-surface-muted text-ink-muted",
  MEDIUM: "bg-status-pending/15 text-status-pending",
  HIGH: "bg-accent-soft text-accent",
  CRITICAL: "bg-negative/10 text-negative",
};

export function PriorityPill({ priority, className }: { priority: TicketPriority; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        STYLES[priority],
        className,
      )}
    >
      {PRIORITY_LABELS[priority]}
    </span>
  );
}
