import type { RefAttributes, SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> &
  RefAttributes<HTMLSelectElement>;

export function Select({ className, children, ref, ...props }: SelectProps) {
  return (
    <select
      ref={ref}
      className={cn(
        "h-10 w-full rounded-xl border border-line bg-surface-muted px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
