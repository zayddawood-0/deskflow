import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.category import Category
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories import category_repository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services import audit_service


def list_categories(db: Session, *, include_inactive: bool) -> list[Category]:
    return category_repository.list_categories(db, include_inactive=include_inactive)


def create_category(db: Session, *, actor: User, payload: CategoryCreate) -> Category:
    if category_repository.get_by_name(db, payload.name) is not None:
        raise ConflictError("A category with this name already exists.")
    category = category_repository.create(db, name=payload.name, description=payload.description)
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.CATEGORY_CREATED,
        entity_type="category",
        entity_id=category.id,
        new_value={"name": category.name},
    )
    return category


def _get_or_404(db: Session, category_id: uuid.UUID) -> Category:
    category = category_repository.get_by_id(db, category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    return category


def update_category(
    db: Session, *, actor: User, category_id: uuid.UUID, payload: CategoryUpdate
) -> Category:
    category = _get_or_404(db, category_id)
    old: dict = {}
    new: dict = {}

    if payload.name is not None and payload.name != category.name:
        existing = category_repository.get_by_name(db, payload.name)
        if existing is not None and existing.id != category.id:
            raise ConflictError("A category with this name already exists.")
        old["name"] = category.name
        category.name = payload.name
        new["name"] = payload.name

    if payload.description is not None and payload.description != category.description:
        old["description"] = category.description
        category.description = payload.description
        new["description"] = payload.description

    if payload.is_active is not None and payload.is_active != category.is_active:
        old["is_active"] = category.is_active
        category.is_active = payload.is_active
        new["is_active"] = payload.is_active

    if new:
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.CATEGORY_UPDATED,
            entity_type="category",
            entity_id=category.id,
            old_value=old,
            new_value=new,
        )
    return category


def deactivate_category(db: Session, *, actor: User, category_id: uuid.UUID) -> None:
    category = _get_or_404(db, category_id)
    if not category.is_active:
        raise NotFoundError("Category not found.")
    category.is_active = False
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.CATEGORY_DEACTIVATED,
        entity_type="category",
        entity_id=category.id,
        old_value={"is_active": True},
        new_value={"is_active": False},
    )
