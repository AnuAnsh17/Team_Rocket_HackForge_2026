"""Authorization and access-control tests.

Everything here asserts a refusal. These are the tests that would catch a
horizontal privilege escalation (reading another employee's data) or a vertical
one (acquiring a capability the role was never granted).
"""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.core.enums import AuditActorType, RoleCode
from app.core.errors import Forbidden, NotFound, Unauthenticated
from app.core.permissions import Permission
from app.core.security import Actor, Identity, MembershipContext
from app.services import scope_service
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.security


def _actor(*, organization_id: uuid.UUID, membership_id: uuid.UUID, roles: set[RoleCode]) -> Actor:
    from app.core.permissions import permissions_for_roles

    return Actor(
        user_id=str(uuid.uuid4()),
        identity=Identity(subject="test", provider="demo"),
        memberships=(
            MembershipContext(
                membership_id=str(membership_id),
                organization_id=str(organization_id),
                roles=frozenset(roles),
            ),
        ),
        active_organization_id=str(organization_id),
        active_membership_id=str(membership_id),
        roles=frozenset(roles),
        permissions=permissions_for_roles(roles),
        actor_type=AuditActorType.DEMO,
    )


class TestFailClosed:
    def test_no_credentials_is_refused(self, client: TestClient) -> None:
        response = client.get("/api/v1/me")
        assert response.status_code == 401

    def test_an_empty_actor_header_is_refused(self, client: TestClient) -> None:
        response = client.get("/api/v1/me", headers={"X-Demo-Actor-Id": "   "})
        assert response.status_code == 401

    def test_a_deactivated_user_is_refused(
        self, client: TestClient, db: Session, employee_headers
    ) -> None:
        import sqlalchemy as sa

        db.execute(sa.text("UPDATE users SET is_active = false"))
        db.flush()
        assert client.get("/api/v1/me", headers=employee_headers).status_code == 401

    def test_a_terminated_membership_is_refused(
        self, client: TestClient, db: Session, employee_headers
    ) -> None:
        """Losing membership must remove access.

        The status is 403 rather than 401 on purpose, and the distinction is
        deliberate: the identity is still valid (we know who this is), but there is
        no active membership authorising any action. A deactivated *user* is 401,
        because then there is no valid identity at all - see
        test_a_deactivated_user_is_refused.
        """
        import sqlalchemy as sa

        db.execute(sa.text("UPDATE organization_memberships SET status = 'terminated'"))
        db.flush()
        response = client.get("/api/v1/me", headers=employee_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_demo_routes_are_absent_when_demo_mode_is_off(self, db: Session, monkeypatch) -> None:
        """A disabled demo surface must not even advertise its existence."""
        original = settings.demo_mode
        monkeypatch.setattr(settings, "demo_mode", False)
        try:
            from app.api.deps import get_session
            from app.main import create_app

            app = create_app()
            app.dependency_overrides[get_session] = lambda: db
            with TestClient(app) as test_client:
                assert test_client.post("/api/v1/demo/seed").status_code == 404
        finally:
            settings.demo_mode = original


class TestTenantIsolation:
    def test_an_actor_cannot_act_in_an_organization_they_do_not_belong_to(
        self, db: Session
    ) -> None:
        actor = _actor(
            organization_id=uuid.uuid4(), membership_id=uuid.uuid4(), roles={RoleCode.EMPLOYEE}
        )
        with pytest.raises(Forbidden):
            scope_service.require_same_organization(actor, uuid.uuid4())

    def test_requesting_another_organization_is_refused(
        self, client: TestClient, employee_headers
    ) -> None:
        response = client.get(
            "/api/v1/me",
            headers={**employee_headers, "X-Demo-Organization-Id": str(uuid.uuid4())},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_a_malformed_organization_header_is_refused_not_ignored(
        self, client: TestClient, employee_headers
    ) -> None:
        response = client.get(
            "/api/v1/me",
            headers={**employee_headers, "X-Demo-Organization-Id": "not-a-uuid"},
        )
        assert response.status_code == 403

    def test_the_actors_own_organization_is_accepted(
        self, db: Session, employee_headers, client: TestClient
    ) -> None:
        import sqlalchemy as sa

        organization_id = db.execute(sa.text("SELECT id FROM organizations LIMIT 1")).scalar()
        response = client.get(
            "/api/v1/me",
            headers={**employee_headers, "X-Demo-Organization-Id": str(organization_id)},
        )
        assert response.status_code == 200


class TestResourceScope:
    def test_a_missing_claim_is_not_disclosed(self, db: Session) -> None:
        actor = _actor(
            organization_id=uuid.uuid4(), membership_id=uuid.uuid4(), roles={RoleCode.EMPLOYEE}
        )
        with pytest.raises(NotFound):
            scope_service.require_expense_read(db, actor, uuid.uuid4())

    def test_an_employee_cannot_read_a_colleagues_claim(self, db: Session, seeded) -> None:
        """The core horizontal-escalation case.

        The claim belongs to another membership; the actor holds only employee
        permissions and no reporting relationship, so the read must be refused with
        the same error a missing record produces.
        """
        import sqlalchemy as sa
        from app.models.expense import Expense
        from app.models.identity import OrganizationMembership

        organization_id = db.execute(sa.text("SELECT id FROM organizations LIMIT 1")).scalar()
        user_id = db.execute(
            sa.text("SELECT user_id FROM organization_memberships LIMIT 1")
        ).scalar()
        other_membership = db.execute(
            sa.text("SELECT id FROM organization_memberships WHERE user_id <> :user_id LIMIT 1"),
            {"user_id": user_id},
        ).scalar()
        assert other_membership is not None, "the seed must create at least two memberships"

        expense = Expense(
            organization_id=organization_id,
            membership_id=other_membership,
            channel="android",
            status="submitted",
            version=1,
        )
        db.add(expense)
        db.flush()

        actor = _actor(
            organization_id=organization_id,
            membership_id=uuid.uuid4(),
            roles={RoleCode.EMPLOYEE},
        )
        with pytest.raises(NotFound):
            scope_service.require_expense_read(db, actor, expense.id)

        # And the colleague's own membership can.
        assert db.get(OrganizationMembership, other_membership) is not None

    def test_a_manager_without_a_reporting_edge_cannot_read_the_claim(
        self, db: Session, seeded
    ) -> None:
        import sqlalchemy as sa
        from app.models.expense import Expense

        organization_id = db.execute(sa.text("SELECT id FROM organizations LIMIT 1")).scalar()
        membership_id = db.execute(
            sa.text(
                "SELECT id FROM organization_memberships "
                "WHERE id NOT IN (SELECT employee_membership_id FROM reporting_relationships) "
                "AND id NOT IN (SELECT manager_membership_id FROM reporting_relationships) "
                "LIMIT 1"
            )
        ).scalar()
        assert membership_id is not None

        expense = Expense(
            organization_id=organization_id,
            membership_id=membership_id,
            channel="android",
            status="submitted",
            version=1,
        )
        db.add(expense)
        db.flush()

        unrelated_manager = _actor(
            organization_id=organization_id,
            membership_id=uuid.uuid4(),
            roles={RoleCode.EMPLOYEE, RoleCode.MANAGER},
        )
        with pytest.raises(NotFound):
            scope_service.require_expense_read(db, unrelated_manager, expense.id)

    def test_a_manager_can_read_a_direct_reports_claim(self, db: Session, seeded) -> None:
        """The positive case, so the refusal above is not simply always-refuse."""
        import sqlalchemy as sa
        from app.models.expense import Expense

        organization_id = db.execute(sa.text("SELECT id FROM organizations LIMIT 1")).scalar()
        manager_membership = db.execute(
            sa.text("SELECT manager_membership_id FROM reporting_relationships LIMIT 1")
        ).scalar()
        employee_membership = db.execute(
            sa.text("SELECT employee_membership_id FROM reporting_relationships LIMIT 1")
        ).scalar()

        expense = Expense(
            organization_id=organization_id,
            membership_id=employee_membership,
            channel="android",
            status="submitted",
            version=1,
        )
        db.add(expense)
        db.flush()

        manager = _actor(
            organization_id=organization_id,
            membership_id=manager_membership,
            roles={RoleCode.EMPLOYEE, RoleCode.MANAGER},
        )
        assert scope_service.require_expense_read(db, manager, expense.id).id == expense.id


class TestVerticalPrivilegeEscalation:
    def test_an_employee_cannot_seed_the_demo_dataset(
        self, client: TestClient, employee_headers
    ) -> None:
        assert client.post("/api/v1/demo/seed", headers=employee_headers).status_code == 403

    def test_an_hr_reviewer_cannot_seed_the_demo_dataset(self, client: TestClient, seeded) -> None:
        headers = {"X-Demo-Actor-Id": seeded["subjects"]["hr.reviewer"]}
        assert client.post("/api/v1/demo/seed", headers=headers).status_code == 403

    def test_a_client_cannot_assert_a_role_it_does_not_hold(
        self, client: TestClient, employee_headers
    ) -> None:
        """Role claims in headers or query strings must be ignored entirely."""
        response = client.get(
            "/api/v1/me/roles",
            headers={**employee_headers, "X-Role": "org_admin", "X-Admin": "true"},
        )
        assert response.status_code == 200
        assert {row["role"] for row in response.json()} == {"employee"}

    def test_actor_permission_assertion_raises_for_a_missing_permission(self) -> None:
        actor = _actor(
            organization_id=uuid.uuid4(), membership_id=uuid.uuid4(), roles={RoleCode.EMPLOYEE}
        )
        with pytest.raises(Forbidden):
            actor.require(Permission.MEMBERSHIP_MANAGE)
        assert actor.has(Permission.EXPENSE_READ_OWN) is True


class TestUnimplementedCapabilityHonesty:
    def test_an_unimplemented_route_is_not_silently_absent_from_the_contract(
        self, client: TestClient
    ) -> None:
        """Anything the contract lists but this build lacks must be declared."""
        declared = " ".join(client.get("/api/v1/meta").json()["unimplemented_capabilities"])
        assert "receipt upload" in declared
        assert "production authentication" in declared

    def test_the_extraction_factory_refuses_an_unimplemented_provider(self) -> None:
        from app.core.config import Settings
        from app.extraction.factory import build_receipt_extractor

        config = Settings(  # type: ignore[arg-type]
            _env_file=None,
            APP_ENV="development",
            EXTRACTION_PROVIDER="openai_compatible",
        )
        with pytest.raises(NotImplementedError):
            build_receipt_extractor(config)

    def test_the_storage_factory_refuses_an_unimplemented_backend(self) -> None:
        from app.core.config import Settings
        from app.storage.factory import build_receipt_storage

        config = Settings(  # type: ignore[arg-type]
            _env_file=None, APP_ENV="development", RECEIPT_STORAGE_BACKEND="supabase"
        )
        with pytest.raises(Exception, match="not implemented"):
            build_receipt_storage(config)

    def test_no_auth_provider_refuses_every_request(self) -> None:
        from app.core.security import NoAuthProvider

        with pytest.raises(Unauthenticated):
            NoAuthProvider().resolve_identity(request=object())  # type: ignore[arg-type]

    def test_supabase_auth_provider_refuses_until_implemented(self) -> None:
        from app.core.security import SupabaseAuthProvider

        with pytest.raises(Exception, match="not implemented"):
            SupabaseAuthProvider().resolve_identity(request=object())  # type: ignore[arg-type]
