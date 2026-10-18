import uuid
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.errors import ValidationError
from app.db.session import get_db
from app.models.enums import SLAState, TicketPriority, TicketStatus, UserRole
from app.models.user import User
from app.schemas.comment import AuditOut
from app.schemas.common import Page, paginate
from app.schemas.ticket import (
    AssignRequest,
    TicketCreate,
    TicketOut,
    TicketStatusUpdate,
    TicketUpdate,
)
from app.services import assignment_service, audit_service, ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])

AnyUser = Annotated[User, Depends(get_current_user)]
AgentDep = Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.ADMIN))]
AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DbDep = Annotated[Session, Depends(get_db)]


def _parse_enum_csv(raw: str | None, enum_cls: type[Enum], field: str) -> list[Enum] | None:
    if not raw:
        return None
    values: list[Enum] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            values.append(enum_cls(token))
        except ValueError as exc:
            raise ValidationError(
                "Invalid filter value.",
                details=[{"field": field, "issue": f"Invalid value: {token}"}],
            ) from exc
    return values or None


@router.get("", response_model=Page[TicketOut])
def list_tickets(
    user: AnyUser,
    db: DbDep,
    status: str | None = None,
    priority: str | None = None,
    category_id: uuid.UUID | None = None,
    assignee_id: str | None = None,
    sla_state: str | None = None,
    q: str | None = None,
    sort: str = "-created_at",
    tab: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[TicketOut]:
    parsed_statuses = _parse_enum_csv(status, TicketStatus, "status")
    parsed_priorities = _parse_enum_csv(priority, TicketPriority, "priority")

    unassigned = False
    parsed_assignee: uuid.UUID | None = None
    if assignee_id == "null":
        unassigned = True
    elif assignee_id:
        try:
            parsed_assignee = uuid.UUID(assignee_id)
        except ValueError as exc:
            raise ValidationError(
                "Invalid filter value.",
                details=[{"field": "assignee_id", "issue": f"Invalid value: {assignee_id}"}],
            ) from exc

    if sla_state is not None and sla_state not in {s.value for s in SLAState}:
        raise ValidationError(
            "Invalid filter value.",
            details=[{"field": "sla_state", "issue": f"Invalid value: {sla_state}"}],
        )

    items, total = ticket_service.list_tickets(
        db,
        user=user,
        statuses=parsed_statuses,
        priorities=parsed_priorities,
        category_id=category_id,
        assignee_id=parsed_assignee,
        unassigned=unassigned,
        tab=tab,
        q=q,
        sla_state_filter=sla_state,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return paginate(items, total, page, page_size)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, user: AnyUser, db: DbDep) -> TicketOut:
    ticket = ticket_service.create(db, actor=user, payload=payload)
    return ticket_service.serialize(db, ticket)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: uuid.UUID, user: AnyUser, db: DbDep) -> TicketOut:
    ticket = ticket_service.get_visible(db, ticket_id, user)
    return ticket_service.serialize(db, ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: uuid.UUID, payload: TicketUpdate, user: AnyUser, db: DbDep
) -> TicketOut:
    ticket = ticket_service.patch(db, actor=user, ticket_id=ticket_id, payload=payload)
    return ticket_service.serialize(db, ticket)


@router.post("/{ticket_id}/status", response_model=TicketOut)
def change_status(
    ticket_id: uuid.UUID, payload: TicketStatusUpdate, user: AnyUser, db: DbDep
) -> TicketOut:
    ticket = ticket_service.transition(db, actor=user, ticket_id=ticket_id, payload=payload)
    return ticket_service.serialize(db, ticket)


@router.post("/{ticket_id}/self-assign", response_model=TicketOut)
def self_assign(ticket_id: uuid.UUID, user: AgentDep, db: DbDep) -> TicketOut:
    ticket = ticket_service.get_visible(db, ticket_id, user)
    ticket = assignment_service.self_assign(db, ticket=ticket, actor=user)
    return ticket_service.serialize(db, ticket)


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(
    ticket_id: uuid.UUID, payload: AssignRequest, user: AdminDep, db: DbDep
) -> TicketOut:
    ticket = ticket_service.get_visible(db, ticket_id, user)
    ticket = assignment_service.admin_assign(
        db, ticket=ticket, assignee_id=payload.assignee_id, actor=user
    )
    return ticket_service.serialize(db, ticket)


@router.post("/{ticket_id}/unassign", response_model=TicketOut)
def unassign_ticket(ticket_id: uuid.UUID, user: AdminDep, db: DbDep) -> TicketOut:
    ticket = ticket_service.get_visible(db, ticket_id, user)
    ticket = assignment_service.unassign(db, ticket=ticket, actor=user)
    return ticket_service.serialize(db, ticket)


@router.get("/{ticket_id}/audit", response_model=Page[AuditOut])
def ticket_audit(
    ticket_id: uuid.UUID,
    user: AnyUser,
    db: DbDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[AuditOut]:
    ticket_service.get_visible(db, ticket_id, user)
    items, total = audit_service.list_entries(
        db, ticket_id=ticket_id, page=page, page_size=page_size
    )
    return paginate(items, total, page, page_size)
