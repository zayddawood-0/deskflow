import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.category import Category
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.common import Items
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])

AnyUser = Annotated[User, Depends(get_current_user)]
AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Items[CategoryOut])
def list_categories(
    user: AnyUser,
    db: DbDep,
    include_inactive: bool = False,
) -> Items[CategoryOut]:
    effective = include_inactive and user.role == UserRole.ADMIN
    categories = category_service.list_categories(db, include_inactive=effective)
    return Items(items=[CategoryOut.model_validate(c) for c in categories])


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, user: AdminDep, db: DbDep) -> Category:
    return category_service.create_category(db, actor=user, payload=payload)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID, payload: CategoryUpdate, user: AdminDep, db: DbDep
) -> Category:
    return category_service.update_category(
        db, actor=user, category_id=category_id, payload=payload
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: uuid.UUID, user: AdminDep, db: DbDep) -> None:
    category_service.deactivate_category(db, actor=user, category_id=category_id)
