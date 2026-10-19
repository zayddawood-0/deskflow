from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from tests.factories import make_category, make_ticket, make_user

SCAN_URL = "/api/v1/internal/sla-scan"


def _token_headers() -> dict[str, str]:
    return {"X-Internal-Token": get_settings().internal_task_token}


def _stale_ticket(db):
    requester = make_user(db, role=UserRole.REQUESTER)
    category = make_category(db)
    return make_ticket(
        db,
        requester=requester,
        category=category,
        created_at=datetime.now(UTC) - timedelta(days=30),
        first_response_minutes=60,
        resolution_minutes=120,
    )


def test_scan_requires_valid_token(client, db) -> None:
    assert client.post(SCAN_URL).status_code == 403
    assert client.post(SCAN_URL, headers={"X-Internal-Token": "wrong"}).status_code == 403


def test_scan_flags_breach_and_writes_audit(client, db) -> None:
    ticket = _stale_ticket(db)

    response = client.post(SCAN_URL, headers=_token_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["scanned"] >= 1
    assert body["newly_breached"] >= 1
    assert body["notifications_created"] >= 1

    db.refresh(ticket)
    assert ticket.sla_breached is True

    entries = (
        db.execute(
            select(AuditLog).where(
                AuditLog.ticket_id == ticket.id, AuditLog.action == "SLA_BREACHED"
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].actor_id is None


def test_scan_is_idempotent(client, db) -> None:
    _stale_ticket(db)

    first = client.post(SCAN_URL, headers=_token_headers()).json()
    second = client.post(SCAN_URL, headers=_token_headers()).json()

    assert first["newly_breached"] >= 1
    assert second["newly_breached"] == 0
    assert second["notifications_created"] == 0
