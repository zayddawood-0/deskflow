"use client";

import { useAuth } from "@/hooks/use-auth";
import { Card } from "@/components/ui/Card";

export default function TicketsPage() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-ink">
          Welcome back, {user?.full_name.split(" ")[0] ?? "there"}!
        </h1>
        <p className="text-sm text-ink-muted">Here&apos;s what&apos;s happening with your queue.</p>
      </div>

      <Card title="Tickets" subtitle="Ticket list lands in Phase 3.">
        <p className="text-sm text-ink-muted">
          The queue, filters and ticket detail views are built in the next phase.
        </p>
      </Card>
    </div>
  );
}
