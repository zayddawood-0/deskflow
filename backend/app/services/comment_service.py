from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError
from app.models.enums import AuditAction, UserRole
from app.models.ticket import Ticket
from app.models.ticket_comment import TicketComment
from app.models.user import User
from app.repositories import comment_repository
from app.schemas.comment import CommentOut
from app.services import audit_service, notification_service


def to_out(comment: TicketComment) -> CommentOut:
    return CommentOut.model_validate(comment)


def list_comments(
    db: Session,
    *,
    ticket: Ticket,
    user: User,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[CommentOut], int]:
    include_internal = user.role != UserRole.REQUESTER
    rows = comment_repository.list_by_ticket(db, ticket.id, include_internal=include_internal)
    total = len(rows)
    start = (page - 1) * page_size
    return [to_out(row) for row in rows[start : start + page_size]], total


def add_comment(
    db: Session,
    *,
    ticket: Ticket,
    author: User,
    body: str,
    is_public: bool,
    notify: bool = True,
) -> TicketComment:
    if not is_public and author.role == UserRole.REQUESTER:
        raise ForbiddenError("Requesters cannot create internal notes.")

    comment = comment_repository.create(
        db,
        ticket_id=ticket.id,
        author_id=author.id,
        author_role=author.role.value,
        body=body,
        is_public=is_public,
    )
    if (
        is_public
        and author.role in (UserRole.AGENT, UserRole.ADMIN)
        and ticket.first_responded_at is None
    ):
        ticket.first_responded_at = datetime.now(UTC)
        db.flush()
    audit_service.record(
        db,
        actor=author,
        action=AuditAction.COMMENT_ADDED if is_public else AuditAction.INTERNAL_NOTE_ADDED,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        new_value={"comment_id": str(comment.id)},
    )
    if is_public and notify:
        notification_service.comment_added(db, ticket=ticket, author=author)
    return comment
