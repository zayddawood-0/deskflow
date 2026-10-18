"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import type { UserRole } from "@/lib/constants";
import { Skeleton } from "@/components/ui/Skeleton";

export interface RoleGuardProps {
  allow?: readonly UserRole[];
  children: React.ReactNode;
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "loading" || !user) {
      return;
    }
    if (status === "unauthenticated") {
      router.replace("/login");
      return;
    }
    if (allow && !allow.includes(user.role)) {
      router.replace("/tickets");
    }
  }, [status, user, allow, router]);

  if (!user) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (allow && !allow.includes(user.role)) {
    return null;
  }

  return children;
}
