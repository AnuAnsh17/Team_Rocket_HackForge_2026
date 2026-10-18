"""Integration tests for policy seeding and the read-only pre-flight endpoint.

The endpoint is the first consumer of the evaluation pipeline, so these tests exercise the
real dependency graph: a verified demo identity resolves to an actor, permissions are
derived server-side, the policy is resolved from the database, and the evaluator runs. The
central claim under test is that the endpoint writes nothing at all.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.config import settings
from app.models.audit import AuditEvent
from app.models.expense import Expense, ExpenseFieldEvidence
from app.models.policy import (
    PolicyAssignment,
    PolicyDocument,
    PolicyRule,
    PolicyVersion,
)
from app.models.receipt import Receipt
from app.schemas.expense import CreateExpenseRequest
from app.services import demo_service
from app.services.actor_service import Identity, resolve_actor
from app.services.expense_workflow_service import create_draft_claim
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

CEILING_EVALUATOR_PROBE = "demo_only_category_ceiling_v1"


@pytest.fixture
def policy_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the fictional demo policy on for one test, as the local flags would."""
    monkeypatch.setattr(settings, "demo_synthetic_policy_enabled", True)
    monkeypatch.setattr(settings, "demo_mode", True)


@pytest.fixture
def policy_seeded(db: Session, policy_enabled: None) -> dict[str, object]:
    result = demo_service.seed_demo_dataset(db)
    organization = _demo_org(db)
    return {
        "organization": organization,
        "subjects": {
            person.key: demo_service.demo_identity_subject(person.key)
            for person in demo_service.DEMO_PEOPLE
        },
        "result": result,
    }


def _demo_org(db: Session):
    from app.models.organization import Organization

    return db.execute(
        select(Organization).where(Organization.slug == demo_service.DEMO_ORG_SLUG)
    ).scalar_one()


def _org_policy_rows(db: Session, organization_id: uuid.UUID) -> dict[str, list]:
    versions = (
        db.execute(
            select(PolicyVersion)
            .join(PolicyDocument, PolicyDocument.id == PolicyVersion.policy_document_id)
            .where(PolicyDocument.organization_id == organization_id)
        )
        .scalars()
        .all()
    )
    version_ids = [v.id for v in versions]
    rules = (
        db.execute(select(PolicyRule).where(PolicyRule.policy_version_id.in_(version_ids)))
        .scalars()
        .all()
        if version_ids
        else []
    )
    assignments = (
        db.execute(
            select(PolicyAssignment).where(PolicyAssignment.organization_id == organization_id)
        )
        .scalars()
        .all()
    )
    documents = (
        db.execute(select(PolicyDocument).where(PolicyDocument.organization_id == organization_id))
        .scalars()
        .all()
    )
    return {
        "documents": list(documents),
        "versions": list(versions),
        "rules": list(rules),
        "assignments": list(assignments),
    }


def _draft_for(
    db: Session,
    person_key: str,
    *,
    category: str = "meal",
    amount: str = "1200.00",
    currency: str = "INR",
    day: int = 12,
) -> Expense:
    actor = resolve_actor(
        db, Identity(subject=demo_service.demo_identity_subject(person_key), provider="demo")
    )
    return create_draft_claim(
        db,
        actor,
        CreateExpenseRequest(
            channel="web",
            merchant="Synthetic test merchant",
            expense_date=date(2026, 8, day),
            amount=Decimal(amount),
            currency=currency,
            category=category,
            business_purpose="Synthetic test claim for the policy pre-flight.",
        ),
    )


class TestSeeding:
    def test_uses_the_existing_demo_organization(self, policy_seeded, db: Session) -> None:
        organization = policy_seeded["organization"]
        assert organization.slug == demo_service.DEMO_ORG_SLUG
        rows = _org_policy_rows(db, organization.id)
        assert rows["documents"] and rows["versions"] and rows["rules"] and rows["assignments"]
        # The fiction lives on the synthetic document. A second document also exists - the
        # unapproved draft the policy-admin review flow demonstrates against - so the real
        # invariant is not "one document" but "one *approved* version, reachable from one
        # assignment", which test_exactly_one_approved_version_governs asserts.
        document_ids = {document.id for document in rows["documents"]}
        assert demo_service._sid("synthetic-policy-document") in document_ids
        expanded_ids = {
            version.policy_document_id
            for version in rows["versions"]
            if version.version_label == demo_service.DEMO_POLICY_VERSION_LABEL
        }
        assert expanded_ids == {demo_service._sid("synthetic-policy-document")}
        # No policy document belongs to any other organization.
        elsewhere = db.execute(
            select(func.count())
            .select_from(PolicyDocument)
            .where(PolicyDocument.organization_id != organization.id)
        ).scalar_one()
        assert elsewhere == 0, "the fictional policy must not leak into another organization"

    def test_every_row_is_labelled_fictional(self, policy_seeded, db: Session) -> None:
        rows = _org_policy_rows(db, policy_seeded["organization"].id)
        synthetic_document_id = demo_service._sid("synthetic-policy-document")

        for document in rows["documents"]:
            assert document.authoritative is False, "a demo policy must not claim authority"
            title = document.title.upper()
            # Each demo document says out loud that it is not the real policy. The wording
            # differs between them, so the check is on the claim, not on one magic word.
            assert any(word in title for word in ("FICTIONAL", "NOT THE APPROVED", "SYNTHETIC"))

        for version in rows["versions"]:
            if version.review_state == "approved":
                assert "DEMO ONLY" in (version.version_label or "").upper()
                assert version.policy_document_id == synthetic_document_id

        synthetic_version_ids = {
            version.id
            for version in rows["versions"]
            if version.policy_document_id == synthetic_document_id
        }
        synthetic_rules = [r for r in rows["rules"] if r.policy_version_id in synthetic_version_ids]
        assert len(synthetic_rules) >= len(demo_service.DEMO_POLICY_CLAUSES)
        for rule in synthetic_rules:
            assert "DEMO ONLY" in rule.title.upper() or "FICTIONAL" in rule.title.upper()
            assert rule.source_clause, "a fictional clause still needs a stable id"
            assert rule.validated_at is not None and rule.validated_by_user_id is not None
            assert rule.source_reference is not None
            assert rule.source_reference["policy_nature"] == "DEMO ONLY - FICTIONAL"

    def test_exactly_one_approved_version_governs(self, policy_seeded, db: Session) -> None:
        rows = _org_policy_rows(db, policy_seeded["organization"].id)
        approved_versions = {v.id for v in rows["versions"] if v.review_state == "approved"}
        assigned = {
            a.policy_version_id for a in rows["assignments"] if a.approval_state == "approved"
        }
        assert len(approved_versions) == 1, "two approved versions would resolve to a conflict"
        assert assigned == approved_versions, "the assignment must point at the approved version"

    def test_previous_fictional_version_is_superseded(self, policy_seeded, db: Session) -> None:
        legacy = db.get(PolicyVersion, demo_service._sid("synthetic-policy-version"))
        if legacy is not None:
            assert legacy.review_state == "superseded"

    def test_ten_category_clauses_are_seeded(self, policy_seeded, db: Session) -> None:
        rows = _org_policy_rows(db, policy_seeded["organization"].id)
        clauses = {r.source_clause for r in rows["rules"] if r.is_active}
        expected = {clause for clause, _category, _amount in demo_service.DEMO_POLICY_CLAUSES}
        assert expected <= clauses
        for rule in rows["rules"]:
            if rule.evaluator_type == CEILING_EVALUATOR_PROBE:
                assert rule.parameters["ceiling_amount"]
                assert rule.category

    def test_seeding_is_idempotent(self, db: Session, policy_enabled: None) -> None:
        demo_service.seed_demo_dataset(db)
        organization = _demo_org(db)
        first = _org_policy_rows(db, organization.id)
        counts_before = (
            len(first["documents"]),
            len(first["versions"]),
            len(first["rules"]),
            len(first["assignments"]),
        )

        demo_service.seed_demo_dataset(db)
        second = _org_policy_rows(db, organization.id)
        counts_after = (
            len(second["documents"]),
            len(second["versions"]),
            len(second["rules"]),
            len(second["assignments"]),
        )
        assert counts_before == counts_after, "a repeat seed duplicated policy rows"
        assert {r.id for r in first["rules"]} == {r.id for r in second["rules"]}

    def test_flag_off_seeds_no_fictional_rule(self, db: Session, monkeypatch) -> None:
        monkeypatch.setattr(settings, "demo_synthetic_policy_enabled", False)
        demo_service.seed_demo_dataset(db)
        organization = _demo_org(db)
        rows = _org_policy_rows(db, organization.id)
        assert not rows["rules"], "no fictional rule may be seeded while the flag is off"


class TestPolicyCheckEndpoint:
    def _headers(self, policy_seeded, person_key: str) -> dict[str, str]:
        return {"X-Demo-Actor-Id": policy_seeded["subjects"][person_key]}

    def test_owner_checks_own_draft(self, client, db, policy_seeded) -> None:
        expense = _draft_for(db, "employee.asha", amount="1200.00")
        response = client.post(
            "/api/v1/policy/check",
            json={"expense_id": str(expense.id)},
            headers=self._headers(policy_seeded, "employee.asha"),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["advisory"] is True
        assert body["advisory_note"]
        assert body["resolved"] is True
        assert body["policy_version"]["version_label"].startswith("DEMO ONLY")
        assert body["findings"], "a resolved policy should produce findings"
        assert any(f["result"] in {"PASS", "FAIL", "UNKNOWN"} for f in body["findings"])
        # The fictional nature of the policy is stated in the finding evidence itself.
        demo_findings = [f for f in body["findings"] if (f.get("evidence") or {}).get("demo_only")]
        assert demo_findings, "the demo rule must identify itself as fictional"

    def test_above_ceiling_reports_fail_with_evidence(self, client, db, policy_seeded) -> None:
        expense = _draft_for(db, "employee.asha", amount="9000.00", category="meal")
        response = client.post(
            "/api/v1/policy/check",
            json={"expense_id": str(expense.id)},
            headers=self._headers(policy_seeded, "employee.asha"),
        )
        assert response.status_code == 200
        failures = [f for f in response.json()["findings"] if f["result"] == "FAIL"]
        assert failures, "a claim above the fictional ceiling must produce a FAIL"
        assert failures[0]["expected"] and failures[0]["observed"]

    def test_uncapped_category_is_unknown_not_pass(self, client, db, policy_seeded) -> None:
        """`medical` has no fictional ceiling, so nothing may pass it."""
        expense = _draft_for(db, "employee.asha", amount="500.00", category="medical")
        response = client.post(
            "/api/v1/policy/check",
            json={"expense_id": str(expense.id)},
            headers=self._headers(policy_seeded, "employee.asha"),
        )
        assert response.status_code == 200
        results = {f["result"] for f in response.json()["findings"]}
        assert "FAIL" not in results
        assert results, "an uncapped category must still produce an honest finding"
        coverage = [
            f for f in response.json()["findings"] if f["rule_id"] == "policy_category_coverage"
        ]
        assert coverage and coverage[0]["result"] == "UNKNOWN"
        assert "no clause" in coverage[0]["message"]

    def test_cross_employee_access_is_denied(self, client, db, policy_seeded) -> None:
        expense = _draft_for(db, "employee.asha", amount="1200.00")
        response = client.post(
            "/api/v1/policy/check",
            json={"expense_id": str(expense.id)},
            headers=self._headers(policy_seeded, "employee.rohit"),
        )
        assert response.status_code in (403, 404), (
            "another employee must not be able to pre-flight a claim they cannot read"
        )

    def test_unknown_expense_is_not_found(self, client, policy_seeded) -> None:
        response = client.post(
            "/api/v1/policy/check",
            json={"expense_id": str(uuid.uuid4())},
            headers=self._headers(policy_seeded, "employee.asha"),
        )
        assert response.status_code in (403, 404)

    def test_missing_actor_is_rejected(self, client, policy_seeded) -> None:
        """Demo mode never falls back to a default identity, so no header is a 401."""
        for payload in (
            {"category": "meal", "amount": "900.00"},
            {"expense_id": str(uuid.uuid4())},
        ):
            response = client.post("/api/v1/policy/check", json=payload)
            assert response.status_code in (401, 403), response.text

    def test_inline_preview_uses_actor_context(self, client, db, policy_seeded) -> None:
        response = client.post(
            "/api/v1/policy/check",
            json={
                "category": "meal",
                "amount": "900.00",
                "currency": "INR",
                "expense_date": "2026-08-05",
            },
            headers=self._headers(policy_seeded, "employee.asha"),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["resolved"] is True
        assert body["findings"]
        # Nothing about the response lets a caller claim another organization.
        assert "organization" not in json_keys(body)

    @pytest.mark.parametrize(
        "field, value",
        [
            ("organization_id", "00000000-0000-0000-0000-000000000000"),
            ("membership_id", "00000000-0000-0000-0000-000000000000"),
            ("policy_version_id", "00000000-0000-0000-0000-000000000000"),
            ("role", "org_admin"),
            ("permissions", ["policy:manage"]),
        ],
    )
    def test_authority_bearing_fields_are_rejected(
        self, client, db, policy_seeded, field: str, value: object
    ) -> None:
        """The request contract forbids identity, role and policy-selection fields.

        These are the fields that would let a caller widen its own authority, so the schema
        rejects them outright rather than ignoring them - a silently dropped field is a
        worse contract than a 422.
        """
        response = client.post(
            "/api/v1/policy/check",
            json={
                "category": "meal",
                "amount": "900.00",
                "currency": "INR",
                "expense_date": "2026-08-05",
                field: value,
            },
            headers=self._headers(policy_seeded, "employee.asha"),
        )
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert any(field in detail["location"] for detail in body["error"]["details"])

    def test_preflight_writes_nothing(self, client, db, policy_seeded) -> None:
        expense = _draft_for(db, "employee.asha", amount="1200.00")

        def snapshot() -> dict[str, object]:
            return {
                "expenses": db.execute(select(func.count()).select_from(Expense)).scalar_one(),
                "audit": db.execute(select(func.count()).select_from(AuditEvent)).scalar_one(),
                "receipts": db.execute(select(func.count()).select_from(Receipt)).scalar_one(),
                "evidence": db.execute(
                    select(func.count()).select_from(ExpenseFieldEvidence)
                ).scalar_one(),
                "rules": db.execute(select(func.count()).select_from(PolicyRule)).scalar_one(),
                "claim": (
                    expense.status,
                    expense.version,
                    expense.updated_at,
                    expense.submitted_at,
                ),
            }

        before = snapshot()
        headers = self._headers(policy_seeded, "employee.asha")
        for payload in (
            {"expense_id": str(expense.id)},
            {
                "category": "meal",
                "amount": "900.00",
                "currency": "INR",
                "expense_date": "2026-08-05",
            },
            {
                "category": "fuel",
                "amount": "99000.00",
                "currency": "USD",
                "expense_date": "2026-08-05",
            },
        ):
            assert (
                client.post("/api/v1/policy/check", json=payload, headers=headers).status_code
                == 200
            )
        db.expire_all()
        assert snapshot() == before, "the pre-flight endpoint must persist nothing"


def json_keys(body: dict) -> set[str]:
    return set(body)
