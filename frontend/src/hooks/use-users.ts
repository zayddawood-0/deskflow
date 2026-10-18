"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { Page, User } from "@/types/api";

export function useAgents() {
  return useQuery({
    queryKey: ["users", { role: "agent" }],
    queryFn: () => api<Page<User>>("/users?role=agent&page_size=100"),
    select: (data) => data.items,
    staleTime: 5 * 60_000,
  });
}
