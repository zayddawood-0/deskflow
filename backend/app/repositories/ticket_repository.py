import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import TicketStatus
from app.models.ticket import Ticket

OPEN_STATUSES = (
    TicketStatus.OPEN,
    TicketStatus.IN_PROGRESS,
    TicketStatus.ON_HOLD,
    TicketStatus.REOPENED,
)


def get_by_id(db: Session, ticket_id: uuid.UUID) -> Ticket | None:
    return db.get(Ticket, ticket_id)


def create(
    db: Session,
    *,
    ticket_number: str,
    title: str,
    description: str,
    category_id: uuid.UUID,
    requester_id: uuid.UUID,
    priority: str,
    first_response_due_at,
    resolution_due_at,
) -> Ticket:
    ticket = Ticket(
        ticket_number=ticket_number,
        title=title,
        description=description,
        category_id=category_id,
        requester_id=requester_id,
        priority=priority,
        status=TicketStatus.OPEN,
        first_response_due_at=first_response_due_at,
        resolution_due_at=resolution_due_at,
    )
    db.add(ticket)
    db.flush()
    return ticket


def list_tickets(
    db: Session,
    *,
    requester_id: uuid.UUID | None = None,
    statuses: list[TicketStatus] | None = None,
    priorities: list[str] | None = None,
    category_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    unassigned: bool = False,
    q: str | None = None,
) -> list[Ticket]:
    stmt = select(Ticket).options(
        joinedload(Ticket.category),
        joinedload(Ticket.requester),
        joinedload(Ticket.assignee),
    )
    if requester_id is not None:
        stmt = stmt.where(Ticket.requester_id == requester_id)
    if statuses:
        stmt = stmt.where(Ticket.status.in_(statuses))
    if priorities:
        stmt = stmt.where(Ticket.priority.in_(priorities))
    if category_id is not None:
        stmt = stmt.where(Ticket.category_id == category_id)
    if unassigned:
        stmt = stmt.where(Ticket.assignee_id.is_(None))
    elif assignee_id is not None:
        stmt = stmt.where(Ticket.assignee_id == assignee_id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Ticket.title.ilike(pattern), Ticket.description.ilike(pattern)))
    stmt = stmt.order_by(Ticket.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def list_open_for_sla(db: Session) -> list[Ticket]:
    stmt = (
        select(Ticket)
        .options(joinedload(Ticket.requester), joinedload(Ticket.assignee))
        .where(Ticket.status.in_(OPEN_STATUSES))
    )
    return list(db.execute(stmt).scalars().all())


def open_load_counts(db: Session) -> dict[uuid.UUID, int]:
    stmt = (
        select(Ticket.assignee_id, func.count())
        .where(Ticket.assignee_id.is_not(None), Ticket.status.in_(OPEN_STATUSES))
        .group_by(Ticket.assignee_id)
    )
    return {row[0]: row[1] for row in db.execute(stmt).all()}
