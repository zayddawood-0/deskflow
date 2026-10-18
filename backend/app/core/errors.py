import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("deskflow.errors")


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, *, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = 403


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    status_code = 401


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409


class AlreadyAssignedError(AppError):
    code = "ALREADY_ASSIGNED"
    status_code = 409


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422


class InvalidTransitionError(AppError):
    code = "INVALID_TRANSITION"
    status_code = 409


class ReopenWindowError(AppError):
    code = "REOPEN_WINDOW_EXPIRED"
    status_code = 409


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    status_code = 429


def _envelope(
    code: str, message: str, details: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def _retry_after_seconds(exc: RateLimitExceeded) -> int:
    limit = getattr(exc, "limit", None)
    rate_item = getattr(limit, "limit", None)
    expiry = getattr(rate_item, "get_expiry", None)
    if expiry is not None:
        return int(expiry())
    return 60


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for err in exc.errors():
            loc = err.get("loc", ())
            field = ".".join(str(part) for part in loc if part not in ("body", "query", "path"))
            details.append({"field": field or "body", "issue": err.get("msg", "Invalid value")})
        return JSONResponse(
            status_code=422,
            content=_envelope("VALIDATION_ERROR", "Request validation failed.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        mapping = {
            401: ("UNAUTHORIZED", "Not authenticated."),
            403: ("FORBIDDEN", "You do not have permission to perform this action."),
            404: ("NOT_FOUND", "Resource not found."),
            405: ("NOT_FOUND", "Method not allowed."),
            429: ("RATE_LIMITED", "Too many requests. Try again later."),
        }
        code, default_message = mapping.get(
            exc.status_code, ("INTERNAL_ERROR", "Unexpected error.")
        )
        message = exc.detail if isinstance(exc.detail, str) and exc.detail else default_message
        headers = getattr(exc, "headers", None)
        response = JSONResponse(status_code=exc.status_code, content=_envelope(code, message))
        if headers:
            for key, value in headers.items():
                response.headers[key] = value
        return response

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        retry_after = _retry_after_seconds(exc)
        response = JSONResponse(
            status_code=429,
            content=_envelope("RATE_LIMITED", "Too many requests. Try again later."),
            headers={"Retry-After": str(retry_after)},
        )
        return response

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
