import uuid
from datetime import UTC, date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.comment import AuditOut
from app.schemas.common import Page, paginate
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])

AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[AuditOut])
def list_audit(
    user: AdminDep,
    db: DbDep,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    ticket_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[AuditOut]:
    start = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from is not None else None
    end = datetime.combine(date_to, time.max, tzinfo=UTC) if date_to is not None else None
    items, total = audit_service.list_entries(
        db,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        ticket_id=ticket_id,
        date_from=start,
        date_to=end,
        page=page,
        page_size=page_size,
    )
    return paginate(items, total, page, page_size)
