import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, RefAttributes } from "react";
import { cn } from "@/lib/utils";

const iconButtonVariants = cva(
  "inline-flex size-10 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        surface: "border border-line bg-surface text-ink hover:bg-surface-muted",
        muted: "bg-surface-muted text-ink hover:bg-line/60",
      },
    },
    defaultVariants: {
      variant: "surface",
    },
  },
);

export interface IconButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    RefAttributes<HTMLButtonElement>,
    VariantProps<typeof iconButtonVariants> {
  label: string;
}

export function IconButton({
  className,
  variant,
  label,
  children,
  ref,
  ...props
}: IconButtonProps) {
  return (
    <button
      ref={ref}
      type={props.type ?? "button"}
      aria-label={label}
      title={label}
      className={cn(iconButtonVariants({ variant }), className)}
      {...props}
    >
      {children}
    </button>
  );
}

export { iconButtonVariants };
