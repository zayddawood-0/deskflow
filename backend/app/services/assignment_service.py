import uuid

from sqlalchemy.orm import Session

from app.core.errors import (
    AlreadyAssignedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.models.enums import AuditAction, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories import ticket_repository, user_repository
from app.services import audit_service, notification_service


def pick_least_loaded_agent(db: Session, *, exclude_id: uuid.UUID | None = None) -> User | None:
    candidates = user_repository.list_active_assignables(db)
    if exclude_id is not None:
        candidates = [c for c in candidates if c.id != exclude_id]
    if not candidates:
        return None
    loads = ticket_repository.open_load_counts(db)
    return min(candidates, key=lambda c: (loads.get(c.id, 0), c.created_at))


def auto_assign(db: Session, *, ticket: Ticket) -> User | None:
    agent = pick_least_loaded_agent(db)
    if agent is None:
        return None
    ticket.assignee_id = agent.id
    ticket.auto_assigned = True
    db.flush()
    audit_service.record(
        db,
        actor=None,
        action=AuditAction.AUTO_ASSIGNED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_value={"assignee_id": None},
        new_value={"assignee_id": str(agent.id)},
    )
    notification_service.assignment_changed(db, ticket=ticket, new_assignee=agent, actor=None)
    return agent


def self_assign(db: Session, *, ticket: Ticket, actor: User) -> Ticket:
    if ticket.assignee_id == actor.id:
        raise AlreadyAssignedError("This ticket is already assigned to you.")
    if ticket.assignee_id is not None:
        raise ConflictError("This ticket is already assigned to someone else.")
    ticket.assignee_id = actor.id
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.ASSIGNED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_value={"assignee_id": None},
        new_value={"assignee_id": str(actor.id)},
    )
    notification_service.assignment_changed(db, ticket=ticket, new_assignee=actor, actor=actor)
    return ticket


def admin_assign(db: Session, *, ticket: Ticket, assignee_id: uuid.UUID, actor: User) -> Ticket:
    target = user_repository.get_by_id(db, assignee_id)
    if (
        target is None
        or not target.is_active
        or target.role not in (UserRole.AGENT, UserRole.ADMIN)
    ):
        raise ValidationError("Assignee must be an active agent or admin.")
    old_assignee_id = ticket.assignee_id
    ticket.assignee_id = target.id
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.ASSIGNED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_value={"assignee_id": str(old_assignee_id) if old_assignee_id else None},
        new_value={"assignee_id": str(target.id)},
    )
    notification_service.assignment_changed(db, ticket=ticket, new_assignee=target, actor=actor)
    return ticket


def unassign(db: Session, *, ticket: Ticket, actor: User) -> Ticket:
    previous = ticket.assignee_id
    if previous is None:
        raise NotFoundError("This ticket has no assignee.")
    ticket.assignee_id = None
    ticket.auto_assigned = False
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.UNASSIGNED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_value={"assignee_id": str(previous)},
        new_value={"assignee_id": None},
    )
    notification_service.unassigned(db, ticket=ticket, actor=actor)
    return ticket
