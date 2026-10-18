import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.enums import AuditAction, TicketPriority
from app.models.sla_policy import SlaPolicy
from app.models.user import User
from app.repositories import sla_policy_repository
from app.schemas.sla_policy import SlaPolicyUpdate
from app.services import audit_service

_SLA_NAMESPACE = uuid.UUID("6f6a1d9e-2b6f-4f2a-9d3a-7c5b1e4f8a21")


def policy_entity_id(priority: TicketPriority) -> uuid.UUID:
    value = priority.value if hasattr(priority, "value") else str(priority)
    return uuid.uuid5(_SLA_NAMESPACE, f"sla_policy:{value}")


def list_policies(db: Session) -> list[SlaPolicy]:
    return sla_policy_repository.list_all(db)


def update_policy(
    db: Session, *, actor: User, priority: TicketPriority, payload: SlaPolicyUpdate
) -> SlaPolicy:
    policy = sla_policy_repository.get(db, priority)
    if policy is None:
        raise NotFoundError("SLA policy not found.")
    old_value = {
        "first_response_minutes": policy.first_response_minutes,
        "resolution_minutes": policy.resolution_minutes,
    }
    policy.first_response_minutes = payload.first_response_minutes
    policy.resolution_minutes = payload.resolution_minutes
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.SLA_POLICY_UPDATED,
        entity_type="sla_policy",
        entity_id=policy_entity_id(policy.priority),
        old_value=old_value,
        new_value={
            "first_response_minutes": policy.first_response_minutes,
            "resolution_minutes": policy.resolution_minutes,
        },
    )
    return policy
