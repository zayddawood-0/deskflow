import { Ticket } from "lucide-react";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-page p-6">
      <div className="flex size-14 items-center justify-center rounded-card bg-accent text-white shadow-card">
        <Ticket className="size-7" aria-hidden />
      </div>
      <h1 className="text-4xl font-extrabold tracking-tight text-ink">DeskFlow</h1>
      <p className="text-sm text-ink-muted">
        IT helpdesk &amp; ticketing — scaffolding in progress. API health:
        <code className="ml-1 rounded-lg bg-surface-muted px-2 py-0.5">/api/v1/health</code>
      </p>
    </main>
  );
}
