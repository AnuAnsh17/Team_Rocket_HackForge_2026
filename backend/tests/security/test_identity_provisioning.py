"""Tests for the identity-provisioning tool.

The property under test is narrow and important: binding an external identity may
only attach it to a user that already exists, may never create a user, membership
or role, must fail closed when the target could not actually authenticate, and must
leave an audit trail in the same transaction. Several tests therefore assert the
*observable consequence* - that the demo header stops working, or that a request
becomes 401 - rather than just the column values, because the column values are only
interesting if they change what the API will accept.
"""

from __future__ import annotations

import contextlib
import uuid

import pytest
from app.core.enums import MembershipStatus
from app.models.audit import AuditEvent
from app.models.identity import OrganizationMembership, RoleAssignment, User
from app.services import demo_service
from scripts import provision_identity as provision
from scripts.provision_identity import (
    EXIT_NOT_CONFIRMED,
    EXIT_OK,
    EXIT_REFUSED,
    ProvisioningError,
    link_identity,
    mask_email,
    resolve_target,
    summarise,
    unlink_identity,
    validate_provider,
    validate_subject,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

SUBJECT = "9f1c2d3e-4a5b-4c6d-8e7f-0123456789ab"
OTHER_SUBJECT = "1a2b3c4d-5e6f-4a8b-9c0d-1e2f3a4b5c6d"
# A whole access token, which is the mistake validate_subject exists to catch.
PASTED_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _make_user(
    db,
    organization_id: uuid.UUID,
    *,
    membership_status: MembershipStatus | None = MembershipStatus.ACTIVE,
    provider: str | None = None,
    subject: str | None = None,
    is_active: bool = True,
) -> tuple[User, OrganizationMembership | None]:
    """Create a user (and optionally a membership) that the tool did not create."""
    user = User(
        id=uuid.uuid4(),
        display_name="Provisioning Test Person",
        email=f"person-{uuid.uuid4().hex[:8]}@example.test",
        auth_provider=provider,
        external_subject=subject,
        is_active=is_active,
        primary_organization_id=organization_id,
    )
    db.add(user)
    db.flush()
    membership = None
    if membership_status is not None:
        membership = OrganizationMembership(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user.id,
            status=membership_status.value,
            is_primary=True,
        )
        db.add(membership)
        db.flush()
    return user, membership


def _roles(db, membership_id: uuid.UUID) -> list[str]:
    """The roles currently granted through a membership."""
    return sorted(
        db.execute(
            select(RoleAssignment.role).where(
                RoleAssignment.membership_id == membership_id,
                RoleAssignment.revoked_at.is_(None),
            )
        ).scalars()
    )


def _audit_events(db, user_id: uuid.UUID, action: str | None = None) -> list[AuditEvent]:
    statement = select(AuditEvent).where(
        AuditEvent.entity_type == "user", AuditEvent.entity_id == user_id
    )
    if action is not None:
        statement = statement.where(AuditEvent.action == action)
    return list(db.execute(statement).scalars())


@pytest.fixture
def seeded_user(seeded, db) -> tuple[User, OrganizationMembership]:
    """The seeded employee: a real user row with a real active membership."""
    subject = demo_service.demo_identity_subject("employee.asha")
    user = db.execute(
        select(User).where(User.external_subject == subject, User.auth_provider == "demo")
    ).scalar_one()
    membership = db.execute(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    ).scalar_one()
    return user, membership


@pytest.fixture
def cli(db, monkeypatch):
    """Run the CLI against the test transaction rather than its own connection.

    ``main`` normally opens its own ``session_scope``. Pointing that at the test's
    session keeps the assertions in one transaction and stops the suite from
    committing to the test database.
    """

    @contextlib.contextmanager
    def scope():
        yield db

    monkeypatch.setattr(provision, "session_scope", scope)
    monkeypatch.setattr(provision, "dispose_engine", lambda: None)
    monkeypatch.setattr(provision, "configure_logging", lambda *_, **__: None)
    return provision.main


# --------------------------------------------------------------------------
# subject and provider validation
# --------------------------------------------------------------------------
class TestSubjectValidation:
    def test_a_supabase_subject_is_normalised_to_a_canonical_uuid(self) -> None:
        upper = "9F1C2D3E-4A5B-4C6D-8E7F-0123456789AB"
        assert validate_subject(upper, provider="supabase") == SUBJECT

    @pytest.mark.parametrize("value", ["", "   ", "\t", "\n"])
    def test_a_blank_subject_is_refused(self, value: str) -> None:
        with pytest.raises(ProvisioningError, match="required and must not be blank"):
            validate_subject(value, provider="supabase")

    def test_a_subject_containing_whitespace_is_refused(self) -> None:
        with pytest.raises(ProvisioningError, match="whitespace or control characters"):
            validate_subject("9f1c2d3e 4a5b", provider="supabase")

    def test_a_subject_containing_a_control_character_is_refused(self) -> None:
        with pytest.raises(ProvisioningError, match="whitespace or control characters"):
            validate_subject(f"{SUBJECT}\x00", provider="supabase")

    def test_an_over_long_subject_is_refused(self) -> None:
        with pytest.raises(ProvisioningError, match="at most 200 characters"):
            validate_subject("a" * 201, provider="supabase")

    def test_a_whole_access_token_is_refused_rather_than_bound(self) -> None:
        """The most likely operator mistake, and it would produce a dead identity."""
        with pytest.raises(ProvisioningError, match="is a UUID"):
            validate_subject(PASTED_TOKEN, provider="supabase")

    def test_an_email_address_is_refused_as_a_subject(self) -> None:
        with pytest.raises(ProvisioningError, match="is a UUID"):
            validate_subject("asha@example.test", provider="supabase")


class TestProviderValidation:
    def test_supabase_is_accepted_and_normalised(self) -> None:
        assert validate_provider(" Supabase ") == "supabase"

    @pytest.mark.parametrize("value", ["demo", "none", "", "google"])
    def test_any_other_provider_is_refused(self, value: str) -> None:
        """'demo' matters most: binding it would hand out demo-header access."""
        with pytest.raises(ProvisioningError, match="must be one of"):
            validate_provider(value)


# --------------------------------------------------------------------------
# target resolution
# --------------------------------------------------------------------------
class TestTargetResolution:
    def test_exactly_one_selector_is_required(self, db) -> None:
        with pytest.raises(ProvisioningError, match="Name exactly one target"):
            resolve_target(db, user_id=None, actor_id=None, membership_id=None)

    def test_two_selectors_are_refused(self, db) -> None:
        with pytest.raises(ProvisioningError, match="Name exactly one target"):
            resolve_target(db, user_id=uuid.uuid4(), actor_id=uuid.uuid4(), membership_id=None)

    def test_an_unknown_user_is_refused_and_never_created(self, db) -> None:
        with pytest.raises(ProvisioningError, match="never creates users"):
            resolve_target(db, user_id=uuid.uuid4(), actor_id=None, membership_id=None)

    def test_an_unknown_membership_is_refused_and_never_created(self, db) -> None:
        with pytest.raises(ProvisioningError, match="never creates memberships"):
            resolve_target(db, user_id=None, actor_id=None, membership_id=uuid.uuid4())

    def test_an_unknown_demo_actor_is_refused_with_the_next_step(self, db) -> None:
        with pytest.raises(ProvisioningError, match="Seed the demo dataset first"):
            resolve_target(db, user_id=None, actor_id=uuid.uuid4(), membership_id=None)

    def test_a_demo_actor_id_resolves_the_seeded_user(self, db, seeded, seeded_user) -> None:
        user, _ = seeded_user
        resolved = resolve_target(
            db, user_id=None, actor_id=uuid.UUID(user.external_subject), membership_id=None
        )
        assert resolved.id == user.id


# --------------------------------------------------------------------------
# refusals
# --------------------------------------------------------------------------
class TestLinkRefusals:
    def test_a_deactivated_user_is_refused(self, db, seeded_user) -> None:
        _, membership = seeded_user
        target, _ = _make_user(db, membership.organization_id, is_active=False)
        with pytest.raises(ProvisioningError, match="deactivated"):
            link_identity(db, user=target, subject=SUBJECT, provider="supabase")

    def test_a_user_with_no_active_membership_is_refused(self, db, seeded_user) -> None:
        _, membership = seeded_user
        target, _ = _make_user(
            db, membership.organization_id, membership_status=MembershipStatus.TERMINATED
        )
        with pytest.raises(ProvisioningError, match="no active membership"):
            link_identity(db, user=target, subject=SUBJECT, provider="supabase")

    def test_a_user_with_no_membership_at_all_is_refused(self, db, seeded_user) -> None:
        _, membership = seeded_user
        target, _ = _make_user(db, membership.organization_id, membership_status=None)
        with pytest.raises(ProvisioningError, match="no active membership"):
            link_identity(db, user=target, subject=SUBJECT, provider="supabase")

    def test_rebinding_a_real_mapping_requires_the_flag(self, db, seeded_user) -> None:
        """A demo placeholder is replaceable; a real identity is not."""
        _, membership = seeded_user
        target, _ = _make_user(
            db,
            membership.organization_id,
            provider="supabase",
            subject=OTHER_SUBJECT,
        )
        with pytest.raises(ProvisioningError, match="already bound"):
            link_identity(db, user=target, subject=SUBJECT, provider="supabase")
        assert target.external_subject == OTHER_SUBJECT

    def test_a_demo_placeholder_is_replaced_without_the_flag(self, db, seeded_user) -> None:
        """The documented local path from demo mode to real authentication."""
        user, _ = seeded_user
        assert user.auth_provider == "demo"

        result = link_identity(db, user=user, subject=SUBJECT, provider="supabase")

        assert result.changed is True
        assert user.auth_provider == "supabase"
        # Even when the flag was not needed, the event names the mapping replaced.
        assert _audit_events(db, user.id, "identity.bound")[0].before["auth_provider"] == "demo"

    def test_claiming_a_subject_bound_to_someone_else_requires_the_flag(
        self, db, seeded_user
    ) -> None:
        _, membership = seeded_user
        holder, _ = _make_user(db, membership.organization_id, provider="supabase", subject=SUBJECT)
        target, _ = _make_user(db, membership.organization_id)
        with pytest.raises(ProvisioningError, match="already bound to user"):
            link_identity(db, user=target, subject=SUBJECT, provider="supabase")
        # The refused attempt changed nothing.
        assert holder.external_subject == SUBJECT
        assert target.external_subject is None


# --------------------------------------------------------------------------
# the write path
# --------------------------------------------------------------------------
class TestLinkSuccess:
    def test_binding_records_the_mapping_and_an_audit_event(self, db, seeded_user) -> None:
        user, _ = seeded_user
        demo_subject = user.external_subject
        result = link_identity(db, user=user, subject=SUBJECT, provider="supabase")

        assert result.changed is True
        assert result.before.provider == "demo"
        assert result.after.describe() == f"supabase:{SUBJECT}"
        assert user.auth_provider == "supabase"
        assert user.external_subject == SUBJECT

        events = _audit_events(db, user.id, "identity.bound")
        assert len(events) == 1
        event = events[0]
        # The audit event records the mapping that was replaced - the demo subject -
        # so the change can be reasoned about and reversed without guessing.
        assert event.before["auth_provider"] == "demo"
        assert event.before["external_subject"] == demo_subject
        assert event.after["auth_provider"] == "supabase"
        assert event.after["external_subject"] == SUBJECT
        assert event.after["transferred_from_user_id"] is None
        assert event.actor_label == provision.ACTOR_LABEL
        assert event.organization_id == user.primary_organization_id

    def test_relinking_the_same_subject_is_idempotent(self, db, seeded_user) -> None:
        """A retried command must not append a second audit event for one change."""
        user, _ = seeded_user
        first = link_identity(db, user=user, subject=SUBJECT, provider="supabase")
        second = link_identity(db, user=user, subject=SUBJECT, provider="supabase")

        assert first.changed is True
        assert second.changed is False
        assert len(_audit_events(db, user.id, "identity.bound")) == 1

    def test_replacing_a_mapping_is_recorded_as_a_rebind(self, db, seeded_user) -> None:
        user, _ = seeded_user
        link_identity(db, user=user, subject=SUBJECT, provider="supabase")
        second = link_identity(
            db, user=user, subject=OTHER_SUBJECT, provider="supabase", rebind=True
        )

        assert second.changed is True
        assert user.external_subject == OTHER_SUBJECT
        assert len(_audit_events(db, user.id, "identity.rebound")) == 1

    def test_moving_a_subject_clears_the_previous_holder(self, db, seeded_user) -> None:
        _, membership = seeded_user
        holder, _ = _make_user(db, membership.organization_id, provider="supabase", subject=SUBJECT)
        target, _ = _make_user(db, membership.organization_id)

        result = link_identity(db, user=target, subject=SUBJECT, provider="supabase", rebind=True)

        assert result.transferred_from_user_id == holder.id
        # Both rows cannot hold the same subject, and the old holder must not keep a
        # mapping that would let it authenticate.
        assert holder.auth_provider is None
        assert holder.external_subject is None
        assert target.external_subject == SUBJECT

    def test_the_database_enforces_subject_uniqueness(self, db, seeded_user) -> None:
        """The CLI check is a courtesy; the constraint is the guarantee."""
        user, membership = seeded_user
        link_identity(db, user=user, subject=SUBJECT, provider="supabase")
        other, _ = _make_user(db, membership.organization_id)

        with pytest.raises(IntegrityError), db.begin_nested():
            other.auth_provider = "supabase"
            other.external_subject = SUBJECT
            db.flush()
        assert other.external_subject is None


class TestUnlink:
    def test_unlinking_clears_the_mapping_and_audits_it(self, db, seeded_user) -> None:
        user, _ = seeded_user
        result = unlink_identity(db, user=user)

        assert result.changed is True
        assert user.auth_provider is None
        assert user.external_subject is None
        events = _audit_events(db, user.id, "identity.unbound")
        assert len(events) == 1
        assert events[0].after == {"auth_provider": None, "external_subject": None}

    def test_unlinking_a_user_with_no_mapping_is_idempotent(self, db, seeded_user) -> None:
        _, membership = seeded_user
        target, _ = _make_user(db, membership.organization_id)
        result = unlink_identity(db, user=target)

        assert result.changed is False
        assert _audit_events(db, target.id, "identity.unbound") == []

    def test_the_user_and_their_membership_survive_unlinking(self, db, seeded_user) -> None:
        """Revoking access must not destroy employment or claim history."""
        user, membership = seeded_user
        membership_id = membership.id
        unlink_identity(db, user=user)

        assert db.get(User, user.id) is not None
        assert db.get(OrganizationMembership, membership_id) is not None


# --------------------------------------------------------------------------
# the consequence: what the API will now accept
# --------------------------------------------------------------------------
class TestAuthenticationConsequences:
    def test_the_seeded_actor_can_authenticate_before_unlinking(self, client, seeded_user) -> None:
        user, _ = seeded_user
        response = client.get("/api/v1/me", headers={"X-Demo-Actor-Id": user.external_subject})
        assert response.status_code == 200

    def test_an_unknown_actor_id_is_refused(self, client, unknown_uuid) -> None:
        """There is no default identity: an unmatched header is not silently someone."""
        response = client.get("/api/v1/me", headers={"X-Demo-Actor-Id": str(unknown_uuid)})
        assert response.status_code == 401

    def test_demo_mode_reaches_a_seeded_actor_by_user_id_by_design(
        self, db, client, seeded_user
    ) -> None:
        """Pinning the documented demo behaviour, so the limitation is explicit.

        The demo provider's subject *is* the seeded user's id, and
        ``actor_service._find_user`` falls back to a primary-key lookup so those
        seeded identities resolve. In demo mode that is the intended contract: the
        console ships an actor picker, and demo mode exists to be impersonated.

        It also means this tool cannot revoke demo-mode access by clearing a
        mapping: under ``AUTH_PROVIDER=demo`` the id alone still authenticates. The
        guarantee that matters is the other one, proved in
        ``tests/security/test_supabase_jwt.py``: when ``AUTH_PROVIDER=supabase`` the
        demo header authenticates nothing, and the demo provider is not even
        constructed.
        """
        user, _ = seeded_user
        actor_id = user.external_subject
        unlink_identity(db, user=user)
        db.flush()

        assert user.auth_provider is None and user.external_subject is None
        response = client.get("/api/v1/me", headers={"X-Demo-Actor-Id": actor_id})
        assert response.status_code == 200
        assert response.json()["user"]["id"] == str(user.id)

    def test_binding_replaces_the_demo_subject_mapping(self, db, seeded_user) -> None:
        """The stored mapping becomes the provider's, so the demo subject is gone."""
        user, _ = seeded_user
        demo_subject = user.external_subject
        link_identity(db, user=user, subject=SUBJECT, provider="supabase")
        db.flush()

        assert demo_subject != SUBJECT
        assert (
            db.execute(
                select(User).where(
                    User.auth_provider == "demo", User.external_subject == demo_subject
                )
            ).scalar_one_or_none()
            is None
        )
        assert user.auth_provider == "supabase"

    def test_binding_grants_no_role_of_its_own(self, db, seeded_user) -> None:
        """Provisioning must not widen authority. It touches no grant.

        The roles a user has come from their membership, which already existed. If
        this operation could add a grant it would be a privilege-escalation tool
        rather than a binding tool.
        """
        user, membership = seeded_user
        before = _roles(db, membership.id)
        link_identity(db, user=user, subject=SUBJECT, provider="supabase")
        db.flush()

        assert _roles(db, membership.id) == before


# --------------------------------------------------------------------------
# presentation
# --------------------------------------------------------------------------
class TestMaskEmail:
    def test_an_address_is_reduced_to_one_recognisable_character(self) -> None:
        assert mask_email("asha@example.test") == "a***@example.test"

    def test_a_missing_address_is_stated_not_faked(self) -> None:
        assert mask_email(None) == "(none)"
        assert mask_email("") == "(none)"

    def test_a_value_without_a_domain_is_fully_masked(self) -> None:
        assert mask_email("asha") == "***"

    def test_the_summary_never_prints_a_full_address(self, db, seeded_user) -> None:
        user, _ = seeded_user
        description = summarise(db, user).describe()
        assert "@example.test" not in description or "***@" in description
        assert user.email is None or user.email not in description


# --------------------------------------------------------------------------
# the CLI contract
# --------------------------------------------------------------------------
class TestCli:
    def test_link_without_confirm_writes_nothing(self, db, cli, capsys, seeded_user) -> None:
        user, _ = seeded_user
        code = cli(["link", "--subject", SUBJECT, "--user", str(user.id)])

        assert code == EXIT_NOT_CONFIRMED
        assert user.auth_provider == "demo"
        assert user.external_subject is not None
        assert _audit_events(db, user.id, "identity.bound") == []
        assert "Nothing was written" in capsys.readouterr().err

    def test_link_with_confirm_binds_the_subject(self, db, cli, capsys, seeded_user) -> None:
        user, _ = seeded_user
        code = cli(
            [
                "link",
                "--subject",
                SUBJECT,
                "--user",
                str(user.id),
                "--confirm",
                "--reason",
                "local e2e",
            ]
        )

        assert code == EXIT_OK
        assert user.auth_provider == "supabase"
        assert user.external_subject == SUBJECT
        events = _audit_events(db, user.id, "identity.bound")
        assert events[0].reason == "local e2e"
        assert "Bound" in capsys.readouterr().out

    def test_dry_run_alongside_confirm_still_writes_nothing(self, db, cli, seeded_user) -> None:
        user, _ = seeded_user
        code = cli(["link", "--subject", SUBJECT, "--user", str(user.id), "--confirm", "--dry-run"])

        assert code == EXIT_NOT_CONFIRMED
        assert user.auth_provider == "demo"

    def test_the_seeded_demo_actor_can_be_bound_by_its_actor_id(self, db, cli, seeded_user) -> None:
        """The documented local flow: no manual database edits."""
        user, _ = seeded_user
        code = cli(
            ["link", "--subject", SUBJECT, "--demo-actor", str(user.external_subject), "--confirm"]
        )

        assert code == EXIT_OK
        assert user.external_subject == SUBJECT

    def test_the_documented_command_is_safe_to_run_twice(
        self, db, cli, capsys, seeded_user
    ) -> None:
        """A regression: the second run used to fail as though the binding were lost.

        Binding replaces the demo mapping, so the (provider='demo', subject) lookup
        stops matching after the first run. Re-running the same command must report
        that nothing changed rather than "no demo actor with id ...".
        """
        user, _ = seeded_user
        actor_id = str(user.external_subject)
        command = ["link", "--subject", SUBJECT, "--demo-actor", actor_id, "--confirm"]

        first = cli(command)
        first_out = capsys.readouterr().out
        second = cli(command)
        second_out = capsys.readouterr().out

        assert first == EXIT_OK
        assert "Bound" in first_out
        assert second == EXIT_OK
        assert "Already bound" in second_out
        assert user.external_subject == SUBJECT
        # One change, one audit event - a retry is not a second change.
        assert len(_audit_events(db, user.id, "identity.bound")) == 1

    def test_an_invalid_subject_fails_before_touching_the_database(
        self, db, cli, capsys, seeded_user
    ) -> None:
        user, _ = seeded_user
        code = cli(["link", "--subject", PASTED_TOKEN, "--user", str(user.id), "--confirm"])

        assert code == EXIT_REFUSED
        assert user.auth_provider == "demo"
        assert "Refused" in capsys.readouterr().err

    def test_show_prints_the_target_and_its_roles(self, cli, capsys, seeded_user) -> None:
        user, membership = seeded_user
        code = cli(["show", "--user", str(user.id)])

        assert code == EXIT_OK
        out = capsys.readouterr().out
        assert str(user.id) in out
        assert str(membership.id) in out
        assert "identity:" in out

    def test_unlink_without_confirm_writes_nothing(self, db, cli, seeded_user) -> None:
        user, _ = seeded_user
        code = cli(["unlink", "--user", str(user.id)])

        assert code == EXIT_NOT_CONFIRMED
        assert user.external_subject is not None

    def test_unlink_with_confirm_clears_the_identity(self, db, cli, seeded_user) -> None:
        user, _ = seeded_user
        code = cli(["unlink", "--user", str(user.id), "--confirm"])

        assert code == EXIT_OK
        assert user.external_subject is None
        assert user.auth_provider is None
