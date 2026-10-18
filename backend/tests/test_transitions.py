from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.enums import TicketStatus, UserRole
from app.models.ticket_comment import TicketComment
from tests.factories import auth_header, make_audit_log, make_category, make_ticket, make_user


def _transition(client, ticket, user, to_status: str, note: str | None = None):
    payload: dict = {"status": to_status}
    if note is not None:
        payload["note"] = note
    return client.post(
        f"/api/v1/tickets/{ticket.id}/status", json=payload, headers=auth_header(user)
    )


class TestTransitionRules:
    def test_agent_starts_progress(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = _transition(client, ticket, agent, "IN_PROGRESS")
        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"
        assert response.json()["first_responded_at"] is not None

    def test_requester_cannot_start_progress(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = _transition(client, ticket, requester, "IN_PROGRESS")
        assert response.status_code == 403

    def test_invalid_pair_returns_conflict(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = _transition(client, ticket, agent, "RESOLVED")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_TRANSITION"

    def test_hold_and_resume_accumulates_paused_time(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(
            db, requester=requester, category=category, status=TicketStatus.IN_PROGRESS
        )
        held = _transition(client, ticket, agent, "ON_HOLD")
        assert held.status_code == 200
        assert held.json()["paused_at"] is not None

        ticket.paused_at = datetime.now(UTC) - timedelta(hours=2)
        db.flush()
        resumed = _transition(client, ticket, agent, "IN_PROGRESS")
        assert resumed.status_code == 200
        assert resumed.json()["paused_at"] is None
        assert resumed.json()["total_paused_seconds"] >= 3600

    def test_note_creates_comment(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = _transition(client, ticket, agent, "IN_PROGRESS", note="Looking into it.")
        assert response.status_code == 200
        comment = db.execute(
            select(TicketComment).where(TicketComment.ticket_id == ticket.id)
        ).scalar_one()
        assert comment.body == "Looking into it."
        assert comment.is_public is True


class TestCloseAndReopen:
    def test_requester_closes_resolved_ticket(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        assignee = make_user(db, role=UserRole.AGENT)
        category = make_category(db)
        ticket = make_ticket(
            db,
            requester=requester,
            category=category,
            status=TicketStatus.RESOLVED,
            assignee=assignee,
        )
        response = _transition(client, ticket, requester, "CLOSED")
        assert response.status_code == 200
        assert response.json()["status"] == "CLOSED"

    def test_reopen_within_window(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category, status=TicketStatus.CLOSED)
        make_audit_log(
            db,
            action="STATUS_CHANGED",
            entity_id=ticket.id,
            ticket=ticket,
            new_value={"status": "CLOSED"},
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        response = _transition(client, ticket, requester, "REOPENED")
        assert response.status_code == 200

    def test_reopen_after_window_expires(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category, status=TicketStatus.CLOSED)
        make_audit_log(
            db,
            action="STATUS_CHANGED",
            entity_id=ticket.id,
            ticket=ticket,
            new_value={"status": "CLOSED"},
            created_at=datetime.now(UTC) - timedelta(days=30),
        )
        response = _transition(client, ticket, requester, "REOPENED")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "REOPEN_WINDOW_EXPIRED"
