from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.notification import Notification
from tests.factories import auth_header, make_category, make_ticket, make_user


def _comment_payload(body: str = "Any update on this?", is_public: bool = True) -> dict:
    return {"body": body, "is_public": is_public}


def test_requester_public_comment_notifies_assignee(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    agent = make_user(db, role=UserRole.AGENT)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category, assignee=agent)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload(),
        headers=auth_header(requester),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_public"] is True
    assert body["author"]["id"] == str(requester.id)
    notifications = (
        db.execute(select(Notification).where(Notification.user_id == agent.id)).scalars().all()
    )
    assert any(row.type == "COMMENT_ADDED" for row in notifications)


def test_agent_public_comment_sets_first_response(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    agent = make_user(db, role=UserRole.AGENT)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category, assignee=agent)

    client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload("Looking into it now."),
        headers=auth_header(agent),
    )

    detail = client.get(f"/api/v1/tickets/{ticket.id}", headers=auth_header(agent)).json()
    assert detail["first_responded_at"] is not None


def test_internal_note_does_not_set_first_response(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    agent = make_user(db, role=UserRole.AGENT)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category, assignee=agent)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload("Old AP in room B.", is_public=False),
        headers=auth_header(agent),
    )

    assert response.status_code == 201
    assert response.json()["is_public"] is False
    detail = client.get(f"/api/v1/tickets/{ticket.id}", headers=auth_header(agent)).json()
    assert detail["first_responded_at"] is None


def test_internal_note_hidden_from_requester(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    agent = make_user(db, role=UserRole.AGENT)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category, assignee=agent)
    client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload("Public hello."),
        headers=auth_header(agent),
    )
    client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload("Internal only.", is_public=False),
        headers=auth_header(agent),
    )

    as_requester = client.get(
        f"/api/v1/tickets/{ticket.id}/comments", headers=auth_header(requester)
    ).json()
    assert [item["body"] for item in as_requester["items"]] == ["Public hello."]

    as_agent = client.get(
        f"/api/v1/tickets/{ticket.id}/comments", headers=auth_header(agent)
    ).json()
    assert as_agent["total"] == 2


def test_requester_cannot_create_internal_note(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload("Sneaky note.", is_public=False),
        headers=auth_header(requester),
    )

    assert response.status_code == 403


def test_comment_writes_audit(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    agent = make_user(db, role=UserRole.AGENT)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category, assignee=agent)

    client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload(),
        headers=auth_header(requester),
    )
    client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload("Internal.", is_public=False),
        headers=auth_header(agent),
    )

    actions = {
        row.action
        for row in db.execute(select(AuditLog).where(AuditLog.ticket_id == ticket.id))
        .scalars()
        .all()
    }
    assert "COMMENT_ADDED" in actions
    assert "INTERNAL_NOTE_ADDED" in actions


def test_empty_body_is_rejected(client, db) -> None:
    requester = make_user(db, role=UserRole.REQUESTER)
    category = make_category(db)
    ticket = make_ticket(db, requester=requester, category=category)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json=_comment_payload(""),
        headers=auth_header(requester),
    )

    assert response.status_code == 422


def test_foreign_ticket_is_404(client, db) -> None:
    owner = make_user(db, role=UserRole.REQUESTER)
    stranger = make_user(db, role=UserRole.REQUESTER)
    category = make_category(db)
    ticket = make_ticket(db, requester=owner, category=category)

    response = client.get(f"/api/v1/tickets/{ticket.id}/comments", headers=auth_header(stranger))
    assert response.status_code == 404
