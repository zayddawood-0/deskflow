import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Page, paginate
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[UserOut])
def list_users(
    user: AdminDep,
    db: DbDep,
    role: UserRole | None = None,
    is_active: bool | None = None,
    q: str | None = None,
    sort: str = "-created_at",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[UserOut]:
    items, total = user_service.list_users(
        db, role=role, is_active=is_active, q=q, sort=sort, page=page, page_size=page_size
    )
    return paginate([UserOut.model_validate(item) for item in items], total, page, page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, user: AdminDep, db: DbDep) -> User:
    return user_service.create_user(db, actor=user, payload=payload)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, user: AdminDep, db: DbDep) -> User:
    return user_service.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, payload: UserUpdate, user: AdminDep, db: DbDep) -> User:
    return user_service.update_user(db, actor=user, user_id=user_id, payload=payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: uuid.UUID, user: AdminDep, db: DbDep) -> None:
    user_service.deactivate_user(db, actor=user, user_id=user_id)
