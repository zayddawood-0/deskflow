from app.models.enums import TicketStatus, UserRole
from tests.factories import auth_header, make_category, make_ticket, make_user


class TestAutoAssign:
    def test_least_loaded_agent_wins(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        busy = make_user(db, role=UserRole.AGENT, full_name="Busy Agent")
        free = make_user(db, role=UserRole.AGENT, full_name="Free Agent")
        category = make_category(db)
        make_ticket(db, requester=requester, category=category, assignee=busy)

        response = client.post(
            "/api/v1/tickets",
            json={
                "title": "Needs an assignee",
                "description": "A description long enough for validation.",
                "category_id": str(category.id),
                "auto_assign": True,
            },
            headers=auth_header(requester),
        )
        assert response.status_code == 201
        assert response.json()["assignee"]["id"] == str(free.id)


class TestSelfAssign:
    def test_agent_self_assigns(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/self-assign", headers=auth_header(agent)
        )
        assert response.status_code == 200
        assert response.json()["assignee"]["id"] == str(agent.id)

    def test_self_assign_twice_conflicts(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category, assignee=agent)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/self-assign", headers=auth_header(agent)
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ALREADY_ASSIGNED"

    def test_self_assign_taken_ticket_conflicts(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        other = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category, assignee=other)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/self-assign", headers=auth_header(agent)
        )
        assert response.status_code == 409

    def test_requester_cannot_self_assign(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/self-assign", headers=auth_header(requester)
        )
        assert response.status_code == 403


class TestAdminAssign:
    def test_admin_assigns_active_agent(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/assign",
            json={"assignee_id": str(agent.id)},
            headers=auth_header(admin),
        )
        assert response.status_code == 200
        assert response.json()["assignee"]["id"] == str(agent.id)

    def test_assign_to_requester_rejected(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/assign",
            json={"assignee_id": str(requester.id)},
            headers=auth_header(admin),
        )
        assert response.status_code == 422

    def test_agent_cannot_admin_assign(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(db, requester=requester, category=category)
        response = client.post(
            f"/api/v1/tickets/{ticket.id}/assign",
            json={"assignee_id": str(agent.id)},
            headers=auth_header(agent),
        )
        assert response.status_code == 403

    def test_unassign_and_unassign_again(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        agent = make_user(db, role=UserRole.AGENT)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)
        ticket = make_ticket(
            db,
            requester=requester,
            category=category,
            assignee=agent,
            status=TicketStatus.IN_PROGRESS,
        )
        first = client.post(f"/api/v1/tickets/{ticket.id}/unassign", headers=auth_header(admin))
        assert first.status_code == 200
        assert first.json()["assignee"] is None
        second = client.post(f"/api/v1/tickets/{ticket.id}/unassign", headers=auth_header(admin))
        assert second.status_code == 404
