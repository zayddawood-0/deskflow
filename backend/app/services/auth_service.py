from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    fake_verify_password,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories import refresh_token_repository, user_repository
from app.services import audit_service


class TokenBundle:
    def __init__(self, user: User, access_token: str, expires_in: int, refresh_token: str) -> None:
        self.user = user
        self.access_token = access_token
        self.expires_in = expires_in
        self.refresh_token = refresh_token


def _issue_tokens(db: Session, user: User) -> TokenBundle:
    access_token, expires_in = create_access_token(user_id=user.id, role=user.role.value)
    refresh_token = new_refresh_token()
    refresh_token_repository.create(
        db,
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_token_expiry(),
    )
    return TokenBundle(user, access_token, expires_in, refresh_token)


def register(db: Session, *, email: str, full_name: str, password: str) -> User:
    if user_repository.email_exists(db, email):
        raise ConflictError("A user with this email already exists.")
    return user_repository.create(
        db,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role="requester",
    )


def login(db: Session, *, email: str, password: str) -> TokenBundle:
    user = user_repository.get_by_email(db, email)
    if user is None:
        fake_verify_password(password)
        raise UnauthorizedError("Invalid email or password.")
    if not verify_password(user.hashed_password, password):
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated.")
    return _issue_tokens(db, user)


def refresh(db: Session, *, refresh_token: str) -> TokenBundle:
    if not refresh_token:
        raise UnauthorizedError("Missing refresh token.")
    row = refresh_token_repository.get_valid_by_hash(db, hash_refresh_token(refresh_token))
    if row is None:
        raise UnauthorizedError("Invalid or expired refresh token.")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired refresh token.")
    refresh_token_repository.revoke(db, row)
    return _issue_tokens(db, user)


def logout(db: Session, *, refresh_token: str) -> None:
    if not refresh_token:
        return
    row = refresh_token_repository.get_valid_by_hash(db, hash_refresh_token(refresh_token))
    if row is not None:
        refresh_token_repository.revoke(db, row)


def change_password(
    db: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
    keep_hash: str | None = None,
) -> None:
    if not verify_password(user.hashed_password, current_password):
        raise UnauthorizedError("Current password is incorrect.")
    user.hashed_password = hash_password(new_password)
    db.flush()
    refresh_token_repository.revoke_all_for_user(db, user.id, keep_hash=keep_hash)
    audit_service.record(
        db,
        actor=user,
        action=AuditAction.PASSWORD_CHANGED,
        entity_type="user",
        entity_id=user.id,
    )
