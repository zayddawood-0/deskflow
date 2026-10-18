import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User

_FORBIDDEN_KEYS = {"password", "hashed_password"}


def _strip(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    return {k: v for k, v in values.items() if k not in _FORBIDDEN_KEYS}


def record(
    db: Session,
    *,
    actor: User | None,
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
