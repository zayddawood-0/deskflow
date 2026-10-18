import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from tests.factories import auth_header, make_audit_log, make_category, make_ticket, make_user


class TestTicketAudit:
    def test_requester_views_own_ticket_audit(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        make_audit_log(
            db, action="TICKET_CREATED", entity_id=ticket.id, ticket=ticket, actor=requester
        )
        response = client.get(f"/api/v1/tickets/{ticket.id}/audit", headers=auth_header(requester))
        assert response.status_code == 200
        actions = [entry["action"] for entry in response.json()["items"]]
        assert "TICKET_CREATED" in actions

    def test_foreign_ticket_audit_is_404(self, client, db) -> None:
        owner = make_user(db, role=UserRole.REQUESTER)
        stranger = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=owner, category=category)
        response = client.get(f"/api/v1/tickets/{ticket.id}/audit", headers=auth_header(stranger))
        assert response.status_code == 404


class TestGlobalAudit:
    def test_requester_forbidden(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        assert client.get("/api/v1/audit", headers=auth_header(requester)).status_code == 403

    def test_admin_lists_and_filters(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        make_audit_log(
            db, action="TICKET_CREATED", entity_id=ticket.id, ticket=ticket, actor=requester
        )
        make_audit_log(
            db, action="PRIORITY_CHANGED", entity_id=ticket.id, ticket=ticket, actor=admin
        )
        response = client.get("/api/v1/audit?action=PRIORITY_CHANGED", headers=auth_header(admin))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "PRIORITY_CHANGED"

    def test_filter_by_ticket(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        make_audit_log(
            db, action="TICKET_CREATED", entity_id=ticket.id, ticket=ticket, actor=requester
        )
        response = client.get(
            f"/api/v1/audit?entity_type=ticket&ticket_id={ticket.id}",
            headers=auth_header(admin),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestAuditImmutability:
    def test_update_is_rejected_by_trigger(self, db) -> None:
        entry = make_audit_log(
            db, action="TICKET_CREATED", entity_type="ticket", entity_id=uuid.uuid4()
        )
        with pytest.raises(DBAPIError):
            with db.begin_nested():
                db.execute(
                    text("UPDATE audit_logs SET action = 'HACKED' WHERE id = :id"),
                    {"id": entry.id},
                )
        db.expire_all()
        refreshed = db.get(AuditLog, entry.id)
        assert refreshed is not None
        assert refreshed.action == "TICKET_CREATED"
