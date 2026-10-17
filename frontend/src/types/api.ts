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
