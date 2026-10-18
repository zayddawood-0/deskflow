from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.rate_limit import LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT, limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value="",
        max_age=0,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env == "production",
    )


def _token_response(bundle: auth_service.TokenBundle) -> TokenResponse:
    return TokenResponse(
        access_token=bundle.access_token,
        expires_in=bundle.expires_in,
        user=UserOut.model_validate(bundle.user),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(REGISTER_RATE_LIMIT)
def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = auth_service.register(
        db, email=payload.email, full_name=payload.full_name, password=payload.password
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> TokenResponse:
    bundle = auth_service.login(db, email=payload.email, password=payload.password)
    _set_refresh_cookie(response, bundle.refresh_token)
    return _token_response(bundle)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> TokenResponse:
    cookie = request.cookies.get(REFRESH_COOKIE, "")
    bundle = auth_service.refresh(db, refresh_token=cookie)
    _set_refresh_cookie(response, bundle.refresh_token)
    return _token_response(bundle)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> None:
    cookie = request.cookies.get(REFRESH_COOKIE, "")
    auth_service.logout(db, refresh_token=cookie)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> None:
    cookie = request.cookies.get(REFRESH_COOKIE, "")
    keep_hash = auth_service.hash_refresh_token(cookie) if cookie else None
    auth_service.change_password(
        db,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        keep_hash=keep_hash,
    )
