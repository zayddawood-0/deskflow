import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog


def _apply_filters(
    stmt,
    *,
    ticket_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str | None,
    entity_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    if ticket_id is not None:
        stmt = stmt.where(AuditLog.ticket_id == ticket_id)
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    return stmt


def list_entries(
    db: Session,
    *,
    ticket_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[AuditLog], int]:
    base = select(AuditLog)
    filtered = _apply_filters(
        base,
        ticket_id=ticket_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
    )
    total = db.execute(select(func.count()).select_from(filtered.subquery())).scalar_one()
    stmt = (
        filtered.options(joinedload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all()), total


def last_status_change_time(
    db: Session, ticket_id: uuid.UUID, status_value: str
) -> datetime | None:
    stmt = (
        select(AuditLog.created_at)
        .where(
            AuditLog.ticket_id == ticket_id,
            AuditLog.action == "STATUS_CHANGED",
            AuditLog.new_value["status"].astext == status_value,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
