from app.models.enums import UserRole
from tests.factories import auth_header, make_category, make_user


class TestCategories:
    def test_readable_by_all(self, client, db) -> None:
        for role in (UserRole.REQUESTER, UserRole.AGENT, UserRole.ADMIN):
            user = make_user(db, role=role)
            response = client.get("/api/v1/categories", headers=auth_header(user))
            assert response.status_code == 200
            assert "items" in response.json()

    def test_write_admin_only(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        agent = make_user(db, role=UserRole.AGENT)
        for user in (requester, agent):
            response = client.post(
                "/api/v1/categories", json={"name": "Peripherals"}, headers=auth_header(user)
            )
            assert response.status_code == 403

    def test_create_and_duplicate_name(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        first = client.post(
            "/api/v1/categories", json={"name": "Peripherals"}, headers=auth_header(admin)
        )
        assert first.status_code == 201
        duplicate = client.post(
            "/api/v1/categories", json={"name": "Peripherals"}, headers=auth_header(admin)
        )
        assert duplicate.status_code == 409

    def test_deactivate_keeps_ticket_fk(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        category = make_category(db)
        response = client.delete(f"/api/v1/categories/{category.id}", headers=auth_header(admin))
        assert response.status_code == 204
        listing = client.get(
            "/api/v1/categories?include_inactive=true", headers=auth_header(admin)
        ).json()["items"]
        deactivated = next(item for item in listing if item["id"] == str(category.id))
        assert deactivated["is_active"] is False
        second = client.delete(f"/api/v1/categories/{category.id}", headers=auth_header(admin))
        assert second.status_code == 404

    def test_inactive_category_rejected_on_create(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db, is_active=False)
        response = client.post(
            "/api/v1/tickets",
            json={
                "title": "Cannot use inactive",
                "description": "This description is long enough.",
                "category_id": str(category.id),
            },
            headers=auth_header(requester),
        )
        assert response.status_code == 409


class TestSlaPolicies:
    def test_readable_by_all_writable_by_admin_only(self, client, db) -> None:
        requester = make_user(db, role=UserRole.REQUESTER)
        agent = make_user(db, role=UserRole.AGENT)
        admin = make_user(db, role=UserRole.ADMIN)
        listing = client.get("/api/v1/sla-policies", headers=auth_header(requester))
        assert listing.status_code == 200
        assert len(listing.json()["items"]) == 4

        payload = {"first_response_minutes": 30, "resolution_minutes": 120}
        assert (
            client.put(
                "/api/v1/sla-policies/HIGH", json=payload, headers=auth_header(requester)
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/v1/sla-policies/HIGH", json=payload, headers=auth_header(agent)
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/v1/sla-policies/HIGH", json=payload, headers=auth_header(admin)
            ).status_code
            == 200
        )

    def test_validation_first_greater_than_resolution(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.put(
            "/api/v1/sla-policies/HIGH",
            json={"first_response_minutes": 600, "resolution_minutes": 60},
            headers=auth_header(admin),
        )
        assert response.status_code == 422

    def test_policy_change_affects_new_tickets_only(self, client, db) -> None:
        admin = make_user(db, role=UserRole.ADMIN)
        requester = make_user(db, role=UserRole.REQUESTER)
        category = make_category(db)

        create_body = {
            "title": "SLA policy probe ticket",
            "description": "A description long enough for validation.",
            "category_id": str(category.id),
            "priority": "LOW",
        }
        first = client.post(
            "/api/v1/tickets", json=create_body, headers=auth_header(requester)
        ).json()

        client.put(
            "/api/v1/sla-policies/LOW",
            json={"first_response_minutes": 30, "resolution_minutes": 60},
            headers=auth_header(admin),
        )

        second = client.post(
            "/api/v1/tickets", json=create_body, headers=auth_header(requester)
        ).json()

        assert first["first_response_due_at"] != second["first_response_due_at"]
