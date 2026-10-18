import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    InvalidTransitionError,
    NotFoundError,
    ReopenWindowError,
    ValidationError,
)
from app.models.enums import AuditAction, TicketPriority, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories import (
    audit_repository,
    category_repository,
    counter_repository,
    sla_policy_repository,
    ticket_repository,
)
from app.schemas.common import CategoryRef, UserRef
from app.schemas.ticket import TicketCreate, TicketOut, TicketStatusUpdate, TicketUpdate
from app.services import (
    assignment_service,
    audit_service,
    comment_service,
    notification_service,
    sla_service,
    status_machine,
)

_PRIORITY_RANK = {
    TicketPriority.LOW: 0,
    TicketPriority.MEDIUM: 1,
    TicketPriority.HIGH: 2,
    TicketPriority.CRITICAL: 3,
}


def _to_out(ticket: Ticket, state) -> TicketOut:
    return TicketOut(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        category=CategoryRef.model_validate(ticket.category),
        requester=UserRef.model_validate(ticket.requester),
        assignee=UserRef.model_validate(ticket.assignee) if ticket.assignee is not None else None,
        auto_assigned=ticket.auto_assigned,
        first_response_due_at=ticket.first_response_due_at,
        resolution_due_at=ticket.resolution_due_at,
        first_responded_at=ticket.first_responded_at,
        resolved_at=ticket.resolved_at,
        paused_at=ticket.paused_at,
        total_paused_seconds=ticket.total_paused_seconds,
        sla_state=state,
        sla_breached=ticket.sla_breached,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def serialize(db: Session, ticket: Ticket, now: datetime | None = None) -> TicketOut:
    moment = now or datetime.now(UTC)
    state = sla_service.evaluate_and_persist(db, ticket, moment)
    return _to_out(ticket, state)


def get_visible(db: Session, ticket_id: uuid.UUID, user: User) -> Ticket:
    ticket = ticket_repository.get_by_id(db, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found.")
    if user.role == UserRole.REQUESTER and ticket.requester_id != user.id:
        raise NotFoundError("Ticket not found.")
    return ticket


def create(db: Session, *, actor: User, payload: TicketCreate) -> Ticket:
    category = category_repository.get_by_id(db, payload.category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    if not category.is_active:
        raise ConflictError("This category is inactive and cannot be used for new tickets.")
    policy = sla_policy_repository.get(db, payload.priority)
    if policy is None:
        raise ValidationError("No SLA policy is configured for this priority.")

    now = datetime.now(UTC)
    first_response_due_at, resolution_due_at = sla_service.compute_due_dates(now, policy)
    ticket = ticket_repository.create(
        db,
        ticket_number=counter_repository.next_ticket_number(db),
        title=payload.title,
        description=payload.description,
        category_id=category.id,
        requester_id=actor.id,
        priority=payload.priority,
        first_response_due_at=first_response_due_at,
        resolution_due_at=resolution_due_at,
    )
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.TICKET_CREATED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        new_value={
            "ticket_number": ticket.ticket_number,
            "title": ticket.title,
            "priority": ticket.priority.value,
            "status": ticket.status.value,
        },
    )
    if payload.auto_assign:
        assignment_service.auto_assign(db, ticket=ticket)
    return ticket


def _sort_key(sort: str):
    field = sort.lstrip("-")
    if field == "priority":
        return lambda t: _PRIORITY_RANK[t.priority]
    if field == "due_at":
        return lambda t: t.resolution_due_at
    if field == "updated_at":
        return lambda t: t.updated_at
    return lambda t: t.created_at


def list_tickets(
    db: Session,
    *,
    user: User,
    statuses: list[TicketStatus] | None = None,
    priorities: list[TicketPriority] | None = None,
    category_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    unassigned: bool = False,
    tab: str | None = None,
    q: str | None = None,
    sla_state_filter: str | None = None,
    sort: str = "-created_at",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TicketOut], int]:
    requester_id = user.id if user.role == UserRole.REQUESTER else None

    if tab == "mine":
        if user.role == UserRole.REQUESTER:
            raise ForbiddenError("Requesters cannot use the 'mine' tab.")
        assignee_id = user.id
        unassigned = False
    elif tab == "unassigned":
        if user.role == UserRole.REQUESTER:
            raise ForbiddenError("Requesters cannot use the unassigned tab.")
        assignee_id = None
        unassigned = True

    tickets = ticket_repository.list_tickets(
        db,
        requester_id=requester_id,
        statuses=statuses,
        priorities=[p.value for p in priorities] if priorities else None,
        category_id=category_id,
        assignee_id=assignee_id,
        unassigned=unassigned,
        q=q,
    )

    now = datetime.now(UTC)
    states = {ticket.id: sla_service.evaluate_and_persist(db, ticket, now) for ticket in tickets}
    if sla_state_filter:
        tickets = [t for t in tickets if states[t.id].value == sla_state_filter]

    tickets.sort(key=_sort_key(sort), reverse=sort.startswith("-"))
    total = len(tickets)
    start = (page - 1) * page_size
    page_items = tickets[start : start + page_size]
    return [_to_out(t, states[t.id]) for t in page_items], total


def patch(db: Session, *, actor: User, ticket_id: uuid.UUID, payload: TicketUpdate) -> Ticket:
    ticket = get_visible(db, ticket_id, actor)

    if actor.role == UserRole.REQUESTER:
        if payload.priority is not None or payload.category_id is not None:
            raise ForbiddenError("You are not allowed to change priority or category.")
        if ticket.status not in (TicketStatus.OPEN, TicketStatus.REOPENED):
            raise ConflictError("This ticket can no longer be edited.")

    old_fields: dict = {}
    new_fields: dict = {}
    if payload.title is not None and payload.title != ticket.title:
        old_fields["title"] = ticket.title
        ticket.title = payload.title
        new_fields["title"] = ticket.title
    if payload.description is not None and payload.description != ticket.description:
        old_fields["description"] = ticket.description
        ticket.description = payload.description
        new_fields["description"] = ticket.description
    if old_fields:
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.TICKET_UPDATED,
            entity_type="ticket",
            entity_id=ticket.id,
            ticket_id=ticket.id,
            old_value=old_fields,
            new_value=new_fields,
        )

    if payload.priority is not None and payload.priority != ticket.priority:
        old_priority = ticket.priority.value
        ticket.priority = payload.priority
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.PRIORITY_CHANGED,
            entity_type="ticket",
            entity_id=ticket.id,
            ticket_id=ticket.id,
            old_value={"priority": old_priority},
            new_value={"priority": ticket.priority.value},
        )

    if payload.category_id is not None and payload.category_id != ticket.category_id:
        category = category_repository.get_by_id(db, payload.category_id)
        if category is None:
            raise NotFoundError("Category not found.")
        if not category.is_active:
            raise ConflictError("This category is inactive.")
        previous_category = str(ticket.category_id)
        ticket.category_id = category.id
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.CATEGORY_CHANGED,
            entity_type="ticket",
            entity_id=ticket.id,
            ticket_id=ticket.id,
            old_value={"category_id": previous_category},
            new_value={"category_id": str(category.id)},
        )

    return ticket


def transition(
    db: Session, *, actor: User, ticket_id: uuid.UUID, payload: TicketStatusUpdate
) -> Ticket:
    ticket = get_visible(db, ticket_id, actor)
    from_status = ticket.status
    to_status = payload.status

    roles = status_machine.roles_for(from_status, to_status)
    if roles is None:
        allowed = status_machine.allowed_next(from_status)
        raise InvalidTransitionError(
            f"Transition from {from_status.value} to {to_status.value} is not allowed.",
            details=[
                {
                    "field": "status",
                    "issue": "Allowed next statuses: "
                    + ", ".join(status.value for status in allowed),
                }
            ],
        )
    if actor.role not in roles:
        raise ForbiddenError("You are not allowed to perform this transition.")

    now = datetime.now(UTC)
    if from_status == TicketStatus.CLOSED and to_status == TicketStatus.REOPENED:
        _enforce_reopen_window(db, ticket, now)

    ticket.status = to_status
    db.flush()

    if (
        to_status in (TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD, TicketStatus.RESOLVED)
        and actor.role in status_machine.AGENT_ROLES
        and ticket.first_responded_at is None
    ):
        ticket.first_responded_at = now

    if to_status == TicketStatus.ON_HOLD:
        ticket.paused_at = now
    elif from_status == TicketStatus.ON_HOLD:
        sla_service.apply_resume(ticket, now)

    if to_status == TicketStatus.RESOLVED and ticket.resolved_at is None:
        ticket.resolved_at = now

    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.STATUS_CHANGED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_value={"status": from_status.value},
        new_value={"status": to_status.value},
    )

    if payload.note:
        comment_service.add_comment(
            db,
            ticket=ticket,
            author=actor,
            body=payload.note,
            is_public=True,
            notify=False,
        )

    if to_status == TicketStatus.RESOLVED:
        notification_service.status_changed(
            db, ticket=ticket, recipient=ticket.requester, actor=actor
        )
    elif to_status in (TicketStatus.REOPENED, TicketStatus.CLOSED):
        notification_service.status_changed(
            db, ticket=ticket, recipient=ticket.assignee, actor=actor
        )

    return ticket


def _enforce_reopen_window(db: Session, ticket: Ticket, now: datetime) -> None:
    closed_at = audit_repository.last_status_change_time(db, ticket.id, TicketStatus.CLOSED.value)
    reference = closed_at or ticket.updated_at
    window_seconds = get_settings().reopen_window_days * 86400
    if (now - reference).total_seconds() > window_seconds:
        raise ReopenWindowError(
            "This ticket can no longer be reopened: the reopen window has expired."
        )
