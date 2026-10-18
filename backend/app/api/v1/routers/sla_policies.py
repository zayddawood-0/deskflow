from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import TicketPriority, UserRole
from app.models.sla_policy import SlaPolicy
from app.models.user import User
from app.schemas.common import Items
from app.schemas.sla_policy import SlaPolicyOut, SlaPolicyUpdate
from app.services import sla_policy_service

router = APIRouter(prefix="/sla-policies", tags=["sla-policies"])

AnyUser = Annotated[User, Depends(get_current_user)]
AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Items[SlaPolicyOut])
def list_policies(user: AnyUser, db: DbDep) -> Items[SlaPolicyOut]:
    policies = sla_policy_service.list_policies(db)
    return Items(items=[SlaPolicyOut.model_validate(p) for p in policies])


@router.put("/{priority}", response_model=SlaPolicyOut)
def update_policy(
    priority: TicketPriority, payload: SlaPolicyUpdate, user: AdminDep, db: DbDep
) -> SlaPolicy:
    return sla_policy_service.update_policy(db, actor=user, priority=priority, payload=payload)
