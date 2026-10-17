"""Demo dataset seeding."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from app.services import demo_service
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


class TestSeed:
    def test_seed_creates_the_expected_synthetic_records(self, db: Session) -> None:
        result = demo_service.seed_demo_dataset(db)
        assert result.dataset == demo_service.DEMO_DATASET
        assert result.synthetic is True
        assert result.organizations == 1
        assert result.users == len(demo_service.DEMO_PEOPLE)

    def test_seed_activates_no_policy_rule(self, db: Session) -> None:
        result = demo_service.seed_demo_dataset(db)
        assert result.policy_rules_activated == 0
        active = db.execute(sa.text("SELECT count(*) FROM policy_rules WHERE is_active")).scalar()
        assert active == 0

    def test_seed_creates_no_allowance_limit_or_job_grade(self, db: Session) -> None:
        """Inventing these would fabricate organizational rules."""
        demo_service.seed_demo_dataset(db)
        assert db.execute(sa.text("SELECT count(*) FROM allowance_profile_items")).scalar() == 0
        assert db.execute(sa.text("SELECT count(*) FROM job_grades")).scalar() == 0
        assert db.execute(sa.text("SELECT count(*) FROM allowance_profiles")).scalar() == 0

    def test_seed_creates_no_expense_claim(self, db: Session) -> None:
        """Claims must be created through the application so provenance is written."""
        demo_service.seed_demo_dataset(db)
        assert db.execute(sa.text("SELECT count(*) FROM expenses")).scalar() == 0

    def test_seed_leaves_the_policy_version_unapproved(self, db: Session) -> None:
        demo_service.seed_demo_dataset(db)
        states = db.execute(sa.text("SELECT review_state FROM policy_versions")).scalars().all()
        assert states == ["draft"]

    def test_seed_is_idempotent(self, db: Session) -> None:
        first = demo_service.seed_demo_dataset(db)
        second = demo_service.seed_demo_dataset(db)
        assert first.users == second.users
        assert first.memberships == second.memberships
        count = db.execute(sa.text("SELECT count(*) FROM organization_memberships")).scalar()
        assert count == len(demo_service.DEMO_PEOPLE)

    def test_seed_creates_reporting_relationships_and_role_grants(self, db: Session) -> None:
        demo_service.seed_demo_dataset(db)
        assert db.execute(sa.text("SELECT count(*) FROM reporting_relationships")).scalar() == 2
        managers = db.execute(
            sa.text("SELECT count(*) FROM role_assignments WHERE role = 'manager'")
        ).scalar()
        assert managers == 1

    def test_seed_records_an_audit_event(self, db: Session) -> None:
        demo_service.seed_demo_dataset(db)
        actions = db.execute(sa.text("SELECT action FROM audit_events")).scalars().all()
        assert "demo.seed" in actions

    def test_seed_uses_fictional_names(self, db: Session) -> None:
        demo_service.seed_demo_dataset(db)
        names = db.execute(sa.text("SELECT display_name FROM users")).scalars().all()
        assert names
        assert all("synthetic" in name for name in names)

    def test_seed_creates_no_user_email_address(self, db: Session) -> None:
        """Synthetic data must not invent or embed real-looking contact details."""
        demo_service.seed_demo_dataset(db)
        emails = (
            db.execute(sa.text("SELECT email FROM users WHERE email IS NOT NULL")).scalars().all()
        )
        assert emails == []


class TestReset:
    def test_reset_removes_only_demo_records(self, db: Session) -> None:
        demo_service.seed_demo_dataset(db)
        result = demo_service.reset_demo_dataset(db)
        assert result.organizations_removed == 1
        assert result.users_removed == len(demo_service.DEMO_PEOPLE)
        assert db.execute(sa.text("SELECT count(*) FROM organizations")).scalar() == 0
        assert db.execute(sa.text("SELECT count(*) FROM users")).scalar() == 0

    def test_reset_keeps_audit_history(self, db: Session) -> None:
        """The audit trail is append-only and survives a demo reset."""
        demo_service.seed_demo_dataset(db)
        demo_service.reset_demo_dataset(db)
        actions = db.execute(sa.text("SELECT action FROM audit_events")).scalars().all()
        assert "demo.reset" in actions


class TestDemoRoutes:
    def test_seed_endpoint_requires_authentication(self, client) -> None:
        assert client.post("/api/v1/demo/seed").status_code == 401

    def test_seed_endpoint_refuses_an_employee(self, client, employee_headers) -> None:
        response = client.post("/api/v1/demo/seed", headers=employee_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_seed_endpoint_accepts_an_authorized_admin(self, client, finance_headers) -> None:
        response = client.post("/api/v1/demo/seed", headers=finance_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["synthetic"] is True
        assert body["policy_rules_activated"] == 0

    def test_email_import_route_is_explicitly_not_implemented(
        self, client, finance_headers
    ) -> None:
        response = client.post("/api/v1/demo/import/email", headers=finance_headers)
        assert response.status_code == 501
        assert "not implemented" in response.json()["error"]["message"].lower()
