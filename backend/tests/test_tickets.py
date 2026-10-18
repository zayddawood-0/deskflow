from datetime import UTC, datetime, timedelta

from app.models.enums import TicketPriority, TicketStatus, UserRole
from tests.factories import auth_header, make_category, make_ticket, make_user


def _create_payload(category_id, **overrides) -> dict:
    payload = {
        "title": "Printer is not working",
        "description": "The office printer refuses to print anything at all.",
        "category_id": str(category_id),
        "auto_assign": False,
    }
    payload.update(overrides)
    return payload


class TestTicketCreate:
    def test_create_defaults(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        response = client.post(
            "/api/v1/tickets",
            json=_create_payload(category.id),
            headers=auth_header(requester),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "OPEN"
        assert body["priority"] == "MEDIUM"
        assert body["ticket_number"].startswith("TCK-")
        assert body["assignee"] is None
        assert body["sla_state"] == "ON_TRACK"
        assert body["first_response_due_at"] is not None

    def test_create_writes_audit(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        body = client.post(
            "/api/v1/tickets",
            json=_create_payload(category.id),
            headers=auth_header(requester),
        ).json()
        audit = client.get(
            f"/api/v1/tickets/{body['id']}/audit", headers=auth_header(requester)
        ).json()
        assert any(entry["action"] == "TICKET_CREATED" for entry in audit["items"])

    def test_create_validates_short_title(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        response = client.post(
            "/api/v1/tickets",
            json=_create_payload(category.id, title="no"),
            headers=auth_header(requester),
        )
        assert response.status_code == 422

    def test_auto_assign_picks_agent(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        agent = make_user(db, role=UserRole.AGENT)
        category = make_category(db)
        response = client.post(
            "/api/v1/tickets",
            json=_create_payload(category.id, auto_assign=True),
            headers=auth_header(requester),
        )
        assert response.status_code == 201
        assert response.json()["assignee"]["id"] == str(agent.id)
        assert response.json()["auto_assigned"] is True


class TestTicketVisibility:
    def test_requester_sees_own_detail(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.get(f"/api/v1/tickets/{ticket.id}", headers=auth_header(requester))
        assert response.status_code == 200

    def test_requester_foreign_ticket_is_404(self, client, db) -> None:
        owner = make_user(db, role=UserRole.REQUESTER)
        stranger = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=owner, category=category)
        response = client.get(f"/api/v1/tickets/{ticket.id}", headers=auth_header(stranger))
        assert response.status_code == 404

    def test_requester_list_scoped_to_self(self, client, db) -> None:
        owner = make_user(db, role=UserRole.REQUESTER)
        stranger = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        make_ticket(db, requester=owner, category=category)
        response = client.get("/api/v1/tickets", headers=auth_header(stranger))
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestTicketList:
    def test_filters_and_sorting(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        make_ticket(db, requester=requester, category=category, priority=TicketPriority.CRITICAL)
        make_ticket(db, requester=requester, category=category, priority=TicketPriority.LOW)

        response = client.get("/api/v1/tickets?priority=CRITICAL", headers=auth_header(agent))
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["priority"] == "CRITICAL"

    def test_pagination_envelope(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        for _ in range(3):
            make_ticket(db, requester=requester, category=category)
        response = client.get("/api/v1/tickets?page=1&page_size=2", headers=auth_header(agent))
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["pages"] == 2

    def test_unassigned_filter(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        make_ticket(db, requester=requester, category=category, assignee=agent)
        make_ticket(db, requester=requester, category=category)
        response = client.get("/api/v1/tickets?assignee_id=null", headers=auth_header(agent))
        assert response.json()["total"] == 1

    def test_mine_tab_is_agent_only(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        assert (
            client.get("/api/v1/tickets?tab=mine", headers=auth_header(requester)).status_code
            == 403
        )

    def test_sla_state_filter(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        make_ticket(
            db,
            requester=requester,
            category=category,
            created_at=datetime.now(UTC) - timedelta(days=30),
        )
        response = client.get("/api/v1/tickets?sla_state=BREACHED", headers=auth_header(agent))
        assert response.json()["total"] == 1

    def test_invalid_filter_is_422(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        response = client.get("/api/v1/tickets?sla_state=NOPE", headers=auth_header(agent))
        assert response.status_code == 422


class TestTicketPatch:
    def test_requester_edits_while_open(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.patch(
            f"/api/v1/tickets/{ticket.id}",
            json={"title": "Updated title here"},
            headers=auth_header(requester),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title here"

    def test_requester_cannot_change_priority(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.patch(
            f"/api/v1/tickets/{ticket.id}",
            json={"priority": "CRITICAL"},
            headers=auth_header(requester),
        )
        assert response.status_code == 403

    def test_requester_cannot_edit_moved_ticket(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(
            db, requester=requester, category=category, status=TicketStatus.IN_PROGRESS
        )
        response = client.patch(
            f"/api/v1/tickets/{ticket.id}",
            json={"title": "Try to edit now"},
            headers=auth_header(requester),
        )
        assert response.status_code == 409

    def test_agent_changes_priority_with_audit(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.patch(
            f"/api/v1/tickets/{ticket.id}",
            json={"priority": "HIGH"},
            headers=auth_header(agent),
        )
        assert response.status_code == 200
        audit = client.get(f"/api/v1/tickets/{ticket.id}/audit", headers=auth_header(agent))
        actions = [entry["action"] for entry in audit.json()["items"]]
        assert "PRIORITY_CHANGED" in actions
