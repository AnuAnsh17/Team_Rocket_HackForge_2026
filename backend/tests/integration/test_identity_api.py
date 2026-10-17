"""Authenticated-actor endpoints."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestMe:
    def test_requires_authentication(self, client) -> None:
        response = client.get("/api/v1/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    def test_returns_the_callers_own_membership(self, client, employee_headers) -> None:
        response = client.get("/api/v1/me", headers=employee_headers)
        assert response.status_code == 200
        body = response.json()
        assert "synthetic employee" in body["user"]["display_name"]
        assert body["status"] == "active"

    def test_an_unknown_actor_id_is_refused(self, client) -> None:
        import uuid

        response = client.get("/api/v1/me", headers={"X-Demo-Actor-Id": str(uuid.uuid4())})
        assert response.status_code == 401

    def test_a_malformed_actor_id_is_refused(self, client) -> None:
        response = client.get("/api/v1/me", headers={"X-Demo-Actor-Id": "not-a-uuid"})
        assert response.status_code == 401

    def test_a_finance_admin_gets_their_own_membership_not_someone_elses(
        self, client, finance_headers
    ) -> None:
        body = client.get("/api/v1/me", headers=finance_headers).json()
        assert "finance administrator" in body["user"]["display_name"]

    def test_response_never_exposes_internal_authorization_data(
        self, client, finance_headers
    ) -> None:
        raw = client.get("/api/v1/me", headers=finance_headers).text.lower()
        for forbidden in ("permission", "password", "token", "object_key"):
            assert forbidden not in raw


class TestMyRoles:
    def test_returns_the_actors_own_grants(self, client, finance_headers) -> None:
        rows = client.get("/api/v1/me/roles", headers=finance_headers).json()
        roles = {row["role"] for row in rows}
        assert roles == {"employee", "finance_admin"}
        assert all(row["scope_type"] == "organization" for row in rows)

    def test_an_employee_holds_only_the_employee_role(self, client, employee_headers) -> None:
        rows = client.get("/api/v1/me/roles", headers=employee_headers).json()
        assert {row["role"] for row in rows} == {"employee"}

    def test_requires_authentication(self, client) -> None:
        assert client.get("/api/v1/me/roles").status_code == 401


class TestMyAudit:
    def test_returns_only_the_actors_own_events(self, client, finance_headers) -> None:
        # Seeded again through the API, because that path attributes the resulting
        # audit event to the authenticated actor. The fixture's direct service call
        # passes no actor, so it cannot be used to test actor-scoped reads.
        assert client.post("/api/v1/demo/seed", headers=finance_headers).status_code == 200

        response = client.get("/api/v1/me/audit", headers=finance_headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert items
        assert all(item["actor_type"] == "demo" for item in items)
        # Every returned event belongs to the caller and nobody else.
        assert len({item["actor_user_id"] for item in items}) == 1

    def test_requires_authentication(self, client) -> None:
        assert client.get("/api/v1/me/audit").status_code == 401
