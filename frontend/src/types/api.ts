import type { TicketPriority, TicketStatus, UserRole, SlaState } from "@/lib/constants";

export type { TicketPriority, TicketStatus, UserRole, SlaState };

export interface ErrorDetail {
  field: string;
  issue: string;
}

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: ErrorDetail[];
  };
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface Items<T> {
  items: T[];
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface HealthResponse {
  status: "ok" | "unavailable";
  database: "up" | "down";
  version: string;
}

export interface MessageResponse {
  message: string;
}

export interface CategoryRef {
  id: string;
  name: string;
}

export interface UserRef {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
}

export interface ActorRef {
  id: string;
  full_name: string;
  role: UserRole;
}

export interface Category {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SlaPolicy {
  priority: TicketPriority;
  first_response_minutes: number;
  resolution_minutes: number;
  updated_at: string;
}

export interface Ticket {
  id: string;
  ticket_number: string;
  title: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: CategoryRef;
  requester: UserRef;
  assignee: UserRef | null;
  auto_assigned: boolean;
  first_response_due_at: string;
  resolution_due_at: string;
  first_responded_at: string | null;
  resolved_at: string | null;
  paused_at: string | null;
  total_paused_seconds: number;
  sla_state: SlaState;
  sla_breached: boolean;
  created_at: string;
  updated_at: string;
}

export interface TicketListParams {
  status?: string;
  priority?: string;
  category_id?: string;
  assignee_id?: string;
  sla_state?: string;
  q?: string;
  tab?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface CreateTicketInput {
  title: string;
  description: string;
  category_id: string;
  priority: TicketPriority;
  auto_assign: boolean;
}

export interface AuditEntry {
  id: string;
  actor: ActorRef | null;
  action: string;
  entity_type: string;
  entity_id: string;
  ticket_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  created_at: string;
}
