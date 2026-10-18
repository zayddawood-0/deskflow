"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { AuditEntry, Page, Ticket, TicketListParams, TicketStatus } from "@/types/api";
import type { CreateTicketValues } from "@/schemas/ticket";

function buildQuery(params: TicketListParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "" || value === "all") {
      continue;
    }
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function useTickets(params: TicketListParams) {
  return useQuery({
    queryKey: ["tickets", params],
    queryFn: () => api<Page<Ticket>>(`/tickets${buildQuery(params)}`),
    placeholderData: (previous) => previous,
  });
}

export function useTicket(id: string) {
  return useQuery({
    queryKey: ["ticket", id],
    queryFn: () => api<Ticket>(`/tickets/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: CreateTicketValues) =>
      api<Ticket>("/tickets", { method: "POST", json: values }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
  });
}

function useTicketMutation<TInput>(
  id: string,
  path: string,
  method: "POST" | "PATCH",
  body: (input: TInput) => unknown,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TInput) =>
      api<Ticket>(`/tickets/${id}${path}`, { method, json: body(input) }),
    onSuccess: (ticket) => {
      queryClient.setQueryData(["ticket", id], ticket);
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-audit", id] });
    },
  });
}

export interface TransitionInput {
  status: TicketStatus;
  note?: string;
}

export function useTransitionTicket(id: string) {
  return useTicketMutation<TransitionInput>(id, "/status", "POST", (input) => input);
}

export function useSelfAssign(id: string) {
  return useTicketMutation<void>(id, "/self-assign", "POST", () => undefined);
}

export function useAssignTicket(id: string) {
  return useTicketMutation<{ assignee_id: string }>(id, "/assign", "POST", (input) => input);
}

export function useUnassignTicket(id: string) {
  return useTicketMutation<void>(id, "/unassign", "POST", () => undefined);
}

export function useTicketAudit(id: string) {
  return useQuery({
    queryKey: ["ticket-audit", id],
    queryFn: () => api<Page<AuditEntry>>(`/tickets/${id}/audit?page_size=50`),
    enabled: Boolean(id),
  });
}
