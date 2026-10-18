from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TicketPriority
from app.models.sla_policy import SlaPolicy

PRIORITY_ORDER = [
    TicketPriority.LOW,
    TicketPriority.MEDIUM,
    TicketPriority.HIGH,
    TicketPriority.CRITICAL,
]


def get(db: Session, priority: TicketPriority) -> SlaPolicy | None:
    return db.get(SlaPolicy, priority)


def list_all(db: Session) -> list[SlaPolicy]:
    ranks = {
        priority: index for index, priority in enumerate(["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    }
    policies = list(db.execute(select(SlaPolicy)).scalars().all())
    return sorted(policies, key=lambda p: ranks.get(p.priority.value, 99))
