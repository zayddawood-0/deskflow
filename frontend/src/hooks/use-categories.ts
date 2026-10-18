"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { Category, Items } from "@/types/api";

export function useCategories(includeInactive = false) {
  return useQuery({
    queryKey: ["categories", { includeInactive }],
    queryFn: () =>
      api<Items<Category>>(
        `/categories${includeInactive ? "?include_inactive=true" : ""}`,
      ),
    select: (data) => data.items,
    staleTime: 5 * 60_000,
  });
}
