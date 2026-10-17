import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}

export function Card({
  className,
  title,
  subtitle,
  action,
  children,
  ...props
}: CardProps) {
  return (
    <section
      className={cn("rounded-card border border-line/60 bg-surface p-6 shadow-card", className)}
      {...props}
    >
      {title || action ? (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title ? <h2 className="font-semibold text-ink">{title}</h2> : null}
            {subtitle ? <p className="text-xs text-ink-muted">{subtitle}</p> : null}
          </div>
          {action}
        </header>
      ) : null}
      {children}
    </section>
  );
}
