import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.ticket_comment import TicketComment


def create(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    author_id: uuid.UUID,
    author_role: str,
    body: str,
    is_public: bool,
) -> TicketComment:
    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=author_id,
        author_role=author_role,
        body=body,
        is_public=is_public,
    )
    db.add(comment)
    db.flush()
    return comment


def list_by_ticket(
    db: Session, ticket_id: uuid.UUID, *, include_internal: bool = True
) -> list[TicketComment]:
    stmt = (
        select(TicketComment)
        .options(joinedload(TicketComment.author))
        .where(TicketComment.ticket_id == ticket_id)
        .order_by(TicketComment.created_at.asc())
    )
    if not include_internal:
        stmt = stmt.where(TicketComment.is_public.is_(True))
    return list(db.execute(stmt).scalars().all())
