from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError
from app.models.enums import AuditAction, UserRole
from app.models.ticket import Ticket
from app.models.ticket_comment import TicketComment
from app.models.user import User
from app.repositories import comment_repository
from app.services import audit_service, notification_service


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
