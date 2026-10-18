import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories import audit_repository
from app.schemas.comment import AuditOut
from app.schemas.common import ActorRef


def record(
    db: Session,
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    ticket_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ticket_id=ticket_id,
        old_value=_strip(old_value),
        new_value=_strip(new_value),
    )
    db.add(entry)
    db.flush()
    return entry


_SENSITIVE_KEYS = {"password", "hashed_password"}


def _strip(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    return {key: value for key, value in values.items() if key not in _SENSITIVE_KEYS}


def to_out(entry: AuditLog) -> AuditOut:
    actor = ActorRef.model_validate(entry.actor) if entry.actor is not None else None
    return AuditOut(
        id=entry.id,
        actor=actor,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        ticket_id=entry.ticket_id,
        old_value=entry.old_value,
        new_value=entry.new_value,
        created_at=entry.created_at,
    )


def list_entries(
    db: Session,
    *,
    ticket_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuditOut], int]:
    rows, total = audit_repository.list_entries(
        db,
        ticket_id=ticket_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return [to_out(row) for row in rows], total
