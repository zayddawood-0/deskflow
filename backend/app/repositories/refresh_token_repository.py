import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


def create(
    db: Session, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> RefreshToken:
    row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(row)
    db.flush()
    return row


def get_valid_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    now = datetime.now(UTC)
    return db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    ).scalar_one_or_none()


def revoke(db: Session, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    db.flush()


def revoke_all_for_user(db: Session, user_id: uuid.UUID, *, keep_hash: str | None = None) -> None:
    now = datetime.now(UTC)
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    if keep_hash is not None:
        stmt = stmt.where(RefreshToken.token_hash != keep_hash)
    db.execute(stmt)
    db.flush()
