from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, require_roles
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.models.enums import UserRole
from app.models.user import User


def build_probe_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    admin_dep = require_roles(UserRole.ADMIN)
    agent_dep = require_roles(UserRole.AGENT, UserRole.ADMIN)

    @app.get("/probe/any")
    def any_user(user: Annotated[User, Depends(get_current_user)]) -> dict:
        return {"role": user.role.value}

    @app.get("/probe/admin")
    def admin_only(user: Annotated[User, Depends(admin_dep)]) -> dict:
        return {"role": user.role.value}

    @app.get("/probe/agent-or-admin")
    def agent_or_admin(user: Annotated[User, Depends(agent_dep)]) -> dict:
        return {"role": user.role.value}

    return app


def auth_header(user: User) -> dict[str, str]:
    token, _ = create_access_token(user_id=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


class TestRequireRoles:
    def test_missing_token_401(self, db) -> None:
        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        assert client.get("/probe/admin").status_code == 401

    def test_requester_denied_admin_endpoint_403(self, db) -> None:
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        requester = make_user(db, role=UserRole.REQUESTER)
        response = client.get("/probe/admin", headers=auth_header(requester))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_agent_denied_admin_endpoint_403(self, db) -> None:
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        agent = make_user(db, role=UserRole.AGENT)
        response = client.get("/probe/admin", headers=auth_header(agent))
        assert response.status_code == 403

    def test_admin_allowed_on_admin_endpoint(self, db) -> None:
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.get("/probe/admin", headers=auth_header(admin))
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_agent_allowed_on_agent_or_admin(self, db) -> None:
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        agent = make_user(db, role=UserRole.AGENT)
        response = client.get("/probe/agent-or-admin", headers=auth_header(agent))
        assert response.status_code == 200

    def test_requester_denied_agent_or_admin(self, db) -> None:
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        requester = make_user(db, role=UserRole.REQUESTER)
        response = client.get("/probe/agent-or-admin", headers=auth_header(requester))
        assert response.status_code == 403

    def test_admin_inherits_agent_powers(self, db) -> None:
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        from app.db.session import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.get("/probe/agent-or-admin", headers=auth_header(admin))
        assert response.status_code == 200


class TestInactiveUserTokens:
    def test_inactive_user_token_rejected_after_deactivation(self, db) -> None:
        from app.db.session import get_db
        from tests.factories import make_user

        client = TestClient(build_probe_app())
        client.app.dependency_overrides[get_db] = lambda: db
        user = make_user(db, role=UserRole.AGENT)
        header = auth_header(user)
        assert client.get("/probe/any", headers=header).status_code == 200
        user.is_active = False
        db.flush()
        assert client.get("/probe/any", headers=header).status_code == 401
