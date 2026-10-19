from pydantic import BaseModel


class SlaScanResult(BaseModel):
    scanned: int
    newly_breached: int
    at_risk: int
    notifications_created: int
