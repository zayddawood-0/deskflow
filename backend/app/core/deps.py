import hmac
import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise UnauthorizedError("Invalid or expired token.") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token.")
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    allowed = set(roles)

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise ForbiddenError("You do not have permission to perform this action.")
        return user

    return dependency


def get_internal_token_header(
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings().internal_task_token
    if x_internal_token is None or not hmac.compare_digest(x_internal_token, expected):
        raise ForbiddenError("Invalid internal task token.")
