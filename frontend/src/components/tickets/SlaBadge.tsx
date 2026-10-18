import { SLA_STATE_LABELS, type SlaState } from "@/lib/constants";
import { cn } from "@/lib/utils";

const STYLES: Record<SlaState, string> = {
  ON_TRACK: "bg-status-resolved/10 text-status-resolved",
  AT_RISK: "bg-status-pending/15 text-status-pending",
  BREACHED: "bg-negative/10 text-negative",
};

export function SlaBadge({ state, className }: { state: SlaState; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        STYLES[state],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {SLA_STATE_LABELS[state]}
    </span>
  );
}
