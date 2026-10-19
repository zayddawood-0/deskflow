from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_internal_token_header
from app.db.session import get_db
from app.schemas.internal import SlaScanResult
from app.services import sla_service

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(get_internal_token_header)],
)

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/sla-scan", response_model=SlaScanResult)
def sla_scan(db: DbDep) -> SlaScanResult:
    return SlaScanResult(**sla_service.scan_all_open(db))
