from app.models.enums import UserRole
from tests.factories import auth_header, make_user


class TestUserAdminRbac:
    def test_requester_cannot_list_users(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        response = client.get("/api/v1/users", headers=auth_header(requester))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_agent_cannot_access_users(self, client, db) -> None:
        agent = make_user(db, role=UserRole.AGENT)
        assert client.get("/api/v1/users", headers=auth_header(agent)).status_code == 403
        assert (
            client.post(
                "/api/v1/users",
                json={"email": "x@y.dev", "full_name": "X", "password": "Agent@1234"},
                headers=auth_header(agent),
            ).status_code
            == 403
        )

    def test_unauthenticated_is_401(self, client) -> None:
        assert client.get("/api/v1/users").status_code == 401


class TestUserCrud:
    def test_admin_lists_and_filters_users(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        make_user(db, role=UserRole.AGENT, full_name="Findme Agent")
        response = client.get("/api/v1/users?role=agent", headers=auth_header(admin))
        assert response.status_code == 200
        body = response.json()
        assert {item["role"] for item in body["items"]} == {"agent"}
        assert body["total"] >= 1

    def test_admin_creates_user(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.post(
            "/api/v1/users",
            json={
                "email": "newagent@deskflow.dev",
                "full_name": "New Agent",
                "password": "Agent@1234",
                "role": "agent",
            },
            headers=auth_header(admin),
        )
        assert response.status_code == 201
        assert response.json()["role"] == "agent"

    def test_duplicate_email_conflicts(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        make_user(db, role=UserRole.REQUESTER, email="dupe@deskflow.dev")
        response = client.post(
            "/api/v1/users",
            json={
                "email": "dupe@deskflow.dev",
                "full_name": "Dupe",
                "password": "Agent@1234",
                "role": "agent",
            },
            headers=auth_header(admin),
        )
        assert response.status_code == 409

    def test_weak_password_rejected(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.post(
            "/api/v1/users",
            json={"email": "weak@deskflow.dev", "full_name": "Weak", "password": "short"},
            headers=auth_header(admin),
        )
        assert response.status_code == 422

    def test_patch_role_change(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        target = make_user(db, role=UserRole.REQUESTER)
        response = client.patch(
            f"/api/v1/users/{target.id}", json={"role": "agent"}, headers=auth_header(admin)
        )
        assert response.status_code == 200
        assert response.json()["role"] == "agent"

    def test_admin_cannot_demote_self(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.patch(
            f"/api/v1/users/{admin.id}", json={"role": "agent"}, headers=auth_header(admin)
        )
        assert response.status_code == 409

    def test_admin_cannot_deactivate_self(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.patch(
            f"/api/v1/users/{admin.id}", json={"is_active": False}, headers=auth_header(admin)
        )
        assert response.status_code == 409

    def test_delete_deactivates_and_kills_tokens(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        target = make_user(db, role=UserRole.AGENT)
        header = auth_header(target)
        assert client.get("/api/v1/auth/me", headers=header).status_code == 200
        response = client.delete(f"/api/v1/users/{target.id}", headers=auth_header(admin))
        assert response.status_code == 204
        assert client.get("/api/v1/auth/me", headers=header).status_code == 401

    def test_get_unknown_user_404(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.get(
            "/api/v1/users/11111111-1111-1111-1111-111111111111", headers=auth_header(admin)
        )
        assert response.status_code == 404
