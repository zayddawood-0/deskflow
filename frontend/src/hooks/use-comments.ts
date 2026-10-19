"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { Comment, CreateCommentInput, Page } from "@/types/api";

export function useTicketComments(ticketId: string) {
  return useQuery({
    queryKey: ["ticket-comments", ticketId],
    queryFn: () => api<Page<Comment>>(`/tickets/${ticketId}/comments?page_size=50`),
    enabled: Boolean(ticketId),
  });
}

export function useAddComment(ticketId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCommentInput) =>
      api<Comment>(`/tickets/${ticketId}/comments`, { method: "POST", json: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ticket-comments", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-audit", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
    },
  });
}
