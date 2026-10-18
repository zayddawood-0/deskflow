from fastapi import APIRouter

from app.api.v1.routers.audit import router as audit_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.categories import router as categories_router
from app.api.v1.routers.sla_policies import router as sla_policies_router
from app.api.v1.routers.tickets import router as tickets_router
from app.api.v1.routers.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(categories_router)
api_router.include_router(sla_policies_router)
api_router.include_router(tickets_router)
api_router.include_router(audit_router)
