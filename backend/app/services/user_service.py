import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.repositories import refresh_token_repository, user_repository
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit_service


def list_users(
    db: Session,
    *,
    role: UserRole | None,
    is_active: bool | None,
    q: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    return user_repository.list_users(
        db, role=role, is_active=is_active, q=q, sort=sort, page=page, page_size=page_size
    )


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def create_user(db: Session, *, actor: User, payload: UserCreate) -> User:
    if user_repository.email_exists(db, payload.email):
        raise ConflictError("A user with this email already exists.")
    user = user_repository.create(
        db,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        new_value={"email": user.email, "role": user.role.value},
    )
    return user


def update_user(db: Session, *, actor: User, user_id: uuid.UUID, payload: UserUpdate) -> User:
    user = get_user(db, user_id)
    if user.id == actor.id and (
        (payload.role is not None and payload.role != UserRole.ADMIN) or payload.is_active is False
    ):
        raise ConflictError("You cannot demote or deactivate your own account.")

    if payload.full_name is not None and payload.full_name != user.full_name:
        previous = user.full_name
        user.full_name = payload.full_name
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.USER_UPDATED,
            entity_type="user",
            entity_id=user.id,
            old_value={"full_name": previous},
            new_value={"full_name": user.full_name},
        )

    if payload.role is not None and payload.role != user.role:
        previous_role = user.role.value
        user.role = payload.role
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.ROLE_CHANGED,
            entity_type="user",
            entity_id=user.id,
            old_value={"role": previous_role},
            new_value={"role": user.role.value},
        )

    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        db.flush()
        if not user.is_active:
            refresh_token_repository.revoke_all_for_user(db, user.id)
            audit_service.record(
                db,
                actor=actor,
                action=AuditAction.USER_DEACTIVATED,
                entity_type="user",
                entity_id=user.id,
                old_value={"is_active": True},
                new_value={"is_active": False},
            )
        else:
            audit_service.record(
                db,
                actor=actor,
                action=AuditAction.USER_UPDATED,
                entity_type="user",
                entity_id=user.id,
                old_value={"is_active": False},
                new_value={"is_active": True},
            )

    return user


def deactivate_user(db: Session, *, actor: User, user_id: uuid.UUID) -> None:
    user = get_user(db, user_id)
    if user.id == actor.id:
        raise ConflictError("You cannot deactivate your own account.")
    if not user.is_active:
        return
    user.is_active = False
    db.flush()
    refresh_token_repository.revoke_all_for_user(db, user.id)
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.USER_DEACTIVATED,
        entity_type="user",
        entity_id=user.id,
        old_value={"is_active": True},
        new_value={"is_active": False},
    )
