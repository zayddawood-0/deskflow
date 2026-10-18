import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import create_access_token
from tests.factories import DEFAULT_PASSWORD, make_user


def _register(
    client: TestClient, email: str = "ana@acme.dev", password: str = "Requester@1234"
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Ana Silva", "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


class TestRegister:
    def test_register_creates_requester_and_returns_user(self, client: TestClient) -> None:
        body = _register(client)
        assert body["role"] == "requester"
        assert body["email"] == "ana@acme.dev"
        assert "access_token" not in body
        assert "refresh_token" not in body
        assert "hashed_password" not in body

    def test_register_duplicate_email_conflicts(self, client: TestClient) -> None:
        _register(client)
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "ana@acme.dev", "full_name": "Other", "password": "Requester@1234"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONFLICT"

    def test_register_duplicate_email_case_insensitive(self, client: TestClient) -> None:
        _register(client, email="ana@acme.dev")
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "ANA@ACME.DEV", "full_name": "Other", "password": "Requester@1234"},
        )
        assert response.status_code == 409

    def test_register_weak_password_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@acme.dev", "full_name": "Weak", "password": "short"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert any(d["field"] == "password" for d in body["error"]["details"])

    def test_register_password_requires_uppercase_lowercase_digit(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "weak2@acme.dev", "full_name": "Weak", "password": "alllowercase1"},
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_success_returns_access_and_sets_refresh_cookie(self, client: TestClient) -> None:
        _register(client)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "Requester@1234"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 1800
        assert body["user"]["email"] == "ana@acme.dev"
        assert "refresh_token" not in body
        set_cookie = response.headers["set-cookie"]
        assert "refresh_token=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie
        assert "Path=/api/v1/auth" in set_cookie

    def test_login_wrong_password_generic_401(self, client: TestClient) -> None:
        _register(client)
        wrong_password = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "WrongPass@1"},
        )
        unknown_email = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@acme.dev", "password": "WrongPass@1"},
        )
        assert wrong_password.status_code == 401
        assert unknown_email.status_code == 401
        assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]

    def test_login_inactive_user_rejected(self, client: TestClient, db) -> None:
        make_user(db, email="inactive@acme.dev", password=DEFAULT_PASSWORD, is_active=False)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@acme.dev", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 401

    def test_login_rate_limited_after_5_attempts(self, client: TestClient) -> None:
        _register(client)
        for _ in range(5):
            client.post(
                "/api/v1/auth/login",
                json={"email": "ana@acme.dev", "password": "WrongPass@1"},
            )
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "WrongPass@1"},
        )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert "Retry-After" in response.headers


class TestRefresh:
    def test_refresh_rotates_token_and_revokes_old(self, client: TestClient) -> None:
        _register(client)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "Requester@1234"},
        )
        old_cookie = login.cookies["refresh_token"]
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["expires_in"] == 1800
        new_cookie = response.cookies["refresh_token"]
        assert new_cookie != old_cookie
        client.cookies.set("refresh_token", old_cookie)
        reuse = client.post("/api/v1/auth/refresh", json={})
        assert reuse.status_code == 401

    def test_refresh_rejected_when_missing(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    def test_refresh_rejected_when_unknown_value(self, client: TestClient) -> None:
        client.cookies.set("refresh_token", "rt_totally-made-up")
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 401

    def test_refresh_rejected_when_expired(self, client: TestClient, db) -> None:
        from app.core.security import hash_refresh_token, new_refresh_token
        from app.repositories import refresh_token_repository
        from tests.factories import make_user

        user = make_user(db)
        token = new_refresh_token()
        refresh_token_repository.create(
            db,
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        client.cookies.set("refresh_token", token)
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 401


class TestLogout:
    def test_logout_revokes_refresh_token_and_clears_cookie(self, client: TestClient) -> None:
        _register(client)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "Requester@1234"},
        )
        cookie = login.cookies["refresh_token"]
        response = client.post("/api/v1/auth/logout", json={})
        assert response.status_code == 204
        cleared = response.headers["set-cookie"]
        assert "refresh_token=" in cleared
        assert "Max-Age=0" in cleared
        client.cookies.set("refresh_token", cookie)
        refresh_after = client.post("/api/v1/auth/refresh", json={})
        assert refresh_after.status_code == 401

    def test_logout_is_idempotent(self, client: TestClient) -> None:
        _register(client)
        _login(client, "ana@acme.dev", "Requester@1234")
        assert client.post("/api/v1/auth/logout", json={}).status_code == 204
        assert client.post("/api/v1/auth/logout", json={}).status_code == 204


class TestChangePassword:
    def test_change_password_requires_current_and_revokes_other_sessions(
        self, client: TestClient, db
    ) -> None:
        _register(client)
        session_a = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "Requester@1234"},
        )
        cookie_a = session_a.cookies["refresh_token"]
        header_a = {"Authorization": f"Bearer {session_a.json()['access_token']}"}
        session_b = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "Requester@1234"},
        )
        cookie_b = session_b.cookies["refresh_token"]

        wrong = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Nope@1234", "new_password": "BrandNew@123"},
            headers=header_a,
        )
        assert wrong.status_code == 401

        client.cookies.set("refresh_token", cookie_a)
        ok = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Requester@1234", "new_password": "BrandNew@123"},
            headers=header_a,
        )
        assert ok.status_code == 204

        client.cookies.set("refresh_token", cookie_b)
        assert client.post("/api/v1/auth/refresh", json={}).status_code == 401

        client.cookies.set("refresh_token", cookie_a)
        assert client.post("/api/v1/auth/refresh", json={}).status_code == 200

        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": "ana@acme.dev", "password": "BrandNew@123"},
        )
        assert new_login.status_code == 200

    def test_change_password_weak_new_password_422(self, client: TestClient) -> None:
        _register(client)
        login = _login(client, "ana@acme.dev", "Requester@1234")
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Requester@1234", "new_password": "weak"},
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert response.status_code == 422


class TestMe:
    def test_me_returns_current_user(self, client: TestClient) -> None:
        _register(client)
        body = _login(client, "ana@acme.dev", "Requester@1234")
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == "ana@acme.dev"

    def test_me_requires_token(self, client: TestClient) -> None:
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_rejects_garbage_token(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert response.status_code == 401

    def test_me_rejects_expired_token(self, client: TestClient, db) -> None:
        from tests.factories import make_user

        user = make_user(db)
        settings = get_settings()
        now = datetime.now(UTC)
        expired = jwt.encode(
            {
                "sub": str(user.id),
                "role": user.role.value,
                "iat": now - timedelta(hours=1),
                "exp": now - timedelta(minutes=30),
                "jti": str(uuid.uuid4()),
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert response.status_code == 401

    def test_me_rejects_token_of_deleted_user(self, client: TestClient, db) -> None:
        from tests.factories import make_user

        user = make_user(db)
        token, _ = create_access_token(user_id=user.id, role=user.role.value)
        db.delete(user)
        db.flush()
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
