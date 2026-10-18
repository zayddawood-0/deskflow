import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str | None,
    ticket_id: uuid.UUID | None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        type=notification_type,
        title=title[:120],
        body=body,
        ticket_id=ticket_id,
    )
    db.add(row)
    db.flush()
    return row


def exists(
    db: Session, *, user_id: uuid.UUID, notification_type: str, ticket_id: uuid.UUID
) -> bool:
    stmt = select(Notification.id).where(
        Notification.user_id == user_id,
        Notification.type == notification_type,
        Notification.ticket_id == ticket_id,
    )
    return db.execute(stmt).first() is not None


def list_for_user(
    db: Session, user_id: uuid.UUID, *, unread_only: bool = False, offset: int, limit: int
) -> tuple[list[Notification], int]:
    conditions = [Notification.user_id == user_id]
    if unread_only:
        conditions.append(Notification.is_read.is_(False))
    total = db.execute(
        select(func.count()).select_from(Notification).where(*conditions)
    ).scalar_one()
    stmt = (
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all()), total


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    return db.execute(stmt).scalar_one()


def get_by_id(db: Session, notification_id: uuid.UUID) -> Notification | None:
    return db.get(Notification, notification_id)


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    rows = list(
        db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.is_read = True
    db.flush()
    return len(rows)
