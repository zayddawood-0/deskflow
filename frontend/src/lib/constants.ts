export const TICKET_STATUSES = [
  "OPEN",
  "IN_PROGRESS",
  "ON_HOLD",
  "RESOLVED",
  "CLOSED",
  "REOPENED",
] as const;
export type TicketStatus = (typeof TICKET_STATUSES)[number];

export const TICKET_STATUS_LABELS: Record<TicketStatus, string> = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  ON_HOLD: "On hold",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
  REOPENED: "Reopened",
};

export const STATUS_COLORS: Record<TicketStatus, string> = {
  OPEN: "#5B6B7F",
  IN_PROGRESS: "#F0510F",
  ON_HOLD: "#E8A33D",
  RESOLVED: "#22A06B",
  CLOSED: "#9A9A9A",
  REOPENED: "#7A5AF8",
};

export const TICKET_PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export type TicketPriority = (typeof TICKET_PRIORITIES)[number];

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  CRITICAL: "Critical",
};

export const PRIORITY_COLORS: Record<TicketPriority, string> = {
  LOW: "#7A7A7A",
  MEDIUM: "#E8A33D",
  HIGH: "#F0510F",
  CRITICAL: "#E5481B",
};

export const USER_ROLES = ["requester", "agent", "admin"] as const;
export type UserRole = (typeof USER_ROLES)[number];

export const ROLE_LABELS: Record<UserRole, string> = {
  requester: "Requester",
  agent: "Agent",
  admin: "Admin",
};

export const SLA_STATES = ["ON_TRACK", "AT_RISK", "BREACHED"] as const;
export type SlaState = (typeof SLA_STATES)[number];

export const SLA_STATE_LABELS: Record<SlaState, string> = {
  ON_TRACK: "On track",
  AT_RISK: "At risk",
  BREACHED: "Breached",
};

export const SLA_STATE_COLORS: Record<SlaState, string> = {
  ON_TRACK: "#22A06B",
  AT_RISK: "#E8A33D",
  BREACHED: "#E5481B",
};

export const DEFAULT_PAGE_SIZE = 20;
export const REQUEST_TIMEOUT_MS = 15_000;
