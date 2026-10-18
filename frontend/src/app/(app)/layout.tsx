import { Suspense, type ReactNode } from "react";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppNavbar } from "@/components/layout/AppNavbar";
import { IconRail } from "@/components/layout/IconRail";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-page">
      <AppNavbar />
      <div className="mx-auto flex w-full max-w-[1440px] flex-1 gap-6 px-4 py-6 sm:px-6 lg:py-8">
        <Suspense fallback={<div className="hidden w-16 shrink-0 lg:block" aria-hidden />}>
          <IconRail />
        </Suspense>
        <div className="min-w-0 flex-1">
          <RoleGuard>{children}</RoleGuard>
        </div>
      </div>
    </div>
  );
}
