"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Ticket } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { ROLE_LABELS } from "@/lib/constants";
import { Button } from "@/components/ui/Button";

export function AppNavbar() {
  const router = useRouter();
  const { user, logout } = useAuth();

  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-10 h-[72px] border-b border-line bg-surface">
      <div className="mx-auto flex h-full w-full max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link className="flex items-center gap-2 text-ink" href="/tickets">
          <span className="flex size-9 items-center justify-center rounded-card bg-accent text-white">
            <Ticket className="size-5" aria-hidden />
          </span>
          <span className="text-lg font-extrabold tracking-tight">DeskFlow</span>
        </Link>

        <div className="flex items-center gap-3">
          {user ? (
            <div className="text-right">
              <p className="text-sm font-semibold text-ink">{user.full_name}</p>
              <p className="text-xs text-ink-muted">{ROLE_LABELS[user.role]}</p>
            </div>
          ) : null}
          <Button variant="ghost" size="sm" onClick={onLogout}>
            <LogOut className="size-4" aria-hidden />
            Log out
          </Button>
        </div>
      </div>
    </header>
  );
}
