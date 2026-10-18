"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Settings, Ticket } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/tickets", label: "Tickets", icon: Ticket },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function IconRail() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="hidden w-16 shrink-0 flex-col items-center gap-3 rounded-card bg-surface py-4 lg:flex"
    >
      {ITEMS.map((item) => {
        const active = pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={item.label}
            className={cn(
              "flex size-10 items-center justify-center rounded-full transition-colors",
              active ? "bg-ink text-white" : "text-ink-muted hover:bg-surface-muted",
            )}
          >
            <Icon className="size-5" aria-hidden />
          </Link>
        );
      })}
    </nav>
  );
}
