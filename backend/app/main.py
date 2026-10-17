from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestIdMiddleware, configure_logging
from app.db.session import database_is_up, get_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DeskFlow API",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url=None,
    )
    configure_logging(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router)

    @app.get("/api/v1/health", tags=["health"], response_model=None)
    def health_check(db: Session = Depends(get_db)) -> dict | JSONResponse:
        up = database_is_up(db)
        payload = {
            "status": "ok" if up else "unavailable",
            "database": "up" if up else "down",
            "version": settings.app_version,
        }
        if not up:
            return JSONResponse(status_code=503, content=payload)
        return payload

    return app


app = create_app()
