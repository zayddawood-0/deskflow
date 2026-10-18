from app.models.enums import TicketStatus, UserRole

AGENT_ROLES = {UserRole.AGENT, UserRole.ADMIN}
REQUESTER_ROLES = {UserRole.REQUESTER, UserRole.AGENT, UserRole.ADMIN}

_TRANSITIONS: dict[tuple[TicketStatus, TicketStatus], set[UserRole]] = {
    (TicketStatus.OPEN, TicketStatus.IN_PROGRESS): AGENT_ROLES,
    (TicketStatus.OPEN, TicketStatus.ON_HOLD): AGENT_ROLES,
    (TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD): AGENT_ROLES,
    (TicketStatus.ON_HOLD, TicketStatus.IN_PROGRESS): AGENT_ROLES,
    (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED): AGENT_ROLES,
    (TicketStatus.RESOLVED, TicketStatus.CLOSED): REQUESTER_ROLES,
    (TicketStatus.RESOLVED, TicketStatus.REOPENED): REQUESTER_ROLES,
    (TicketStatus.CLOSED, TicketStatus.REOPENED): REQUESTER_ROLES,
    (TicketStatus.REOPENED, TicketStatus.IN_PROGRESS): AGENT_ROLES,
}

_STATUS_ORDER = [
    TicketStatus.OPEN,
    TicketStatus.IN_PROGRESS,
    TicketStatus.ON_HOLD,
    TicketStatus.RESOLVED,
    TicketStatus.CLOSED,
    TicketStatus.REOPENED,
]


def roles_for(from_status: TicketStatus, to_status: TicketStatus) -> set[UserRole] | None:
    return _TRANSITIONS.get((from_status, to_status))


def allowed_next(from_status: TicketStatus) -> list[TicketStatus]:
    return [status for status in _STATUS_ORDER if (from_status, status) in _TRANSITIONS]
