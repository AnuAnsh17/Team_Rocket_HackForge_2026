"""Bind a verified external identity to a pre-provisioned Proofline user.

Why this is a script and not an endpoint
----------------------------------------
A Supabase user is only useful once a trusted operator has connected the verified
token subject (``sub``) to a *pre-existing* user and membership. Everything that
user may then do is decided by the roles and scope already recorded in the
database, so provisioning grants no authority of its own: it only says "this
external identity is this employee".

That binding is the one operation that must never be reachable over HTTP. An
unauthenticated "link my account" endpoint is an account-takeover primitive, and
an authenticated self-service one lets any user claim any unbound identity. So it
lives here, takes an explicit target that the operator chooses by id, refuses to
create anything, and is recorded as an audit event in the same transaction as the
change.

Usage
-----
    cd backend

    # Who is this, and what are they allowed to do?
    python -m scripts.provision_identity show --user <user-uuid>
    python -m scripts.provision_identity show --demo-actor <demo-actor-uuid>

    # Bind a Supabase subject to the seeded demo actor, for local end-to-end work.
    python -m scripts.provision_identity link \
        --subject <supabase-sub> --demo-actor <demo-actor-uuid> --confirm

    # Bind to an explicitly chosen user, or to the user owning a membership.
    python -m scripts.provision_identity link --subject <sub> --user <user-uuid> --confirm
    python -m scripts.provision_identity link --subject <sub> --membership <membership-uuid> --confirm

    # Reverse it: the user becomes unauthenticatable rather than wrongly identified.
    python -m scripts.provision_identity unlink --user <user-uuid> --confirm

Nothing is written without ``--confirm``: the script prints the exact change it
would make and exits non-zero. ``--rebind`` is required to overwrite a real
identity mapping or to move a subject away from another user, because both are the
kind of change that should be impossible to make by accident. Replacing a *demo*
placeholder mapping does not require it - that is the intended path from demo mode
to real authentication - but the plan still names the mapping being replaced and the
change is still recorded in the audit event.

The operation is deliberately idempotent: re-running the same link reports that
nothing changed rather than appending a second identical audit event.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from dataclasses import dataclass, field

from app.core.enums import AuditActorType, MembershipStatus
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_scope
from app.models.identity import OrganizationMembership, RoleAssignment, User
from app.services.audit_service import audit
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

# Providers this tool may bind. 'demo' is excluded on purpose: demo identities are
# owned by the seeder, and letting an operator rebind a user to the demo provider
# would be a way to hand out demo-header access rather than real authentication.
_ALLOWED_PROVIDERS = ("supabase",)

# Providers whose subject is a UUID. Validating the shape catches the common
# operator mistake of pasting a whole access token, a refresh token or an email
# address into --subject, which would otherwise bind an identity that can never
# authenticate.
_UUID_SUBJECT_PROVIDERS = frozenset({"supabase"})

_PROVIDER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_SUBJECT_MAX_LENGTH = 200  # matches users.external_subject

# Exit codes. 2 is "the operator did not confirm", which is not an error so much
# as an incomplete instruction, and is kept distinct so a wrapper script can tell
# the two apart.
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_NOT_CONFIRMED = 2

ACTOR_LABEL = "provision_identity script"


class ProvisioningError(Exception):
    """A refusal with an operator-readable reason. Nothing has been written."""


@dataclass(frozen=True)
class IdentityMapping:
    """The external identity currently bound to a user, if any."""

    provider: str | None
    subject: str | None

    @property
    def is_bound(self) -> bool:
        return bool(self.provider and self.subject)

    def describe(self) -> str:
        if not self.is_bound:
            return "no external identity bound"
        return f"{self.provider}:{self.subject}"


@dataclass
class TargetSummary:
    """What the operator is about to act on, so the plan is reviewable."""

    user: User
    memberships: list[OrganizationMembership] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)

    @property
    def active_memberships(self) -> list[OrganizationMembership]:
        return [m for m in self.memberships if m.status == MembershipStatus.ACTIVE.value]

    def describe(self) -> str:
        lines = [
            f"user:      {self.user.id}",
            f"name:      {self.user.display_name}",
            f"email:     {mask_email(self.user.email)}",
            f"active:    {self.user.is_active}",
            f"identity:  {IdentityMapping(self.user.auth_provider, self.user.external_subject).describe()}",
        ]
        if self.memberships:
            lines.append("memberships:")
            for membership in self.memberships:
                scope = membership.organization_id
                lines.append(f"  - {membership.id}  status={membership.status}  org={scope}")
        else:
            lines.append("memberships: none")
        lines.append(f"roles:     {', '.join(sorted(set(self.roles))) or 'none'}")
        return "\n".join(lines)


@dataclass(frozen=True)
class LinkResult:
    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    before: IdentityMapping
    after: IdentityMapping
    changed: bool
    transferred_from_user_id: uuid.UUID | None = None


def mask_email(email: str | None) -> str:
    """Reduce an address to something safe to print.

    Email is personal data, so the operator gets enough to recognise the record
    and not enough to harvest it from a terminal scrollback or a log aggregator.
    """
    if not email:
        return "(none)"
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    keep = local[:1]
    return f"{keep}***@{domain}"


def validate_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    if value not in _ALLOWED_PROVIDERS:
        raise ProvisioningError(
            f"--provider must be one of {sorted(_ALLOWED_PROVIDERS)}; got {provider!r}. "
            "Demo identities belong to the seeder, not to this tool."
        )
    if not _PROVIDER_PATTERN.match(value):  # defensive: the allowlist already constrains this
        raise ProvisioningError(f"--provider {provider!r} is not a valid provider name.")
    return value


def validate_subject(subject: str, *, provider: str) -> str:
    """Validate and normalise a token subject.

    A subject is an opaque identifier from the identity provider. It is not a
    secret, but a malformed one produces a user who can never authenticate, so a
    shape the provider is known to reject is refused here instead of silently
    bound.
    """
    value = (subject or "").strip()
    if not value:
        raise ProvisioningError("--subject is required and must not be blank.")
    if len(value) > _SUBJECT_MAX_LENGTH:
        raise ProvisioningError(
            f"--subject must be at most {_SUBJECT_MAX_LENGTH} characters; got {len(value)}."
        )
    if any(character.isspace() or ord(character) < 0x20 for character in value):
        raise ProvisioningError(
            "--subject must not contain whitespace or control characters. "
            "If you pasted a token, use only the 'sub' claim."
        )
    if provider in _UUID_SUBJECT_PROVIDERS:
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ProvisioningError(
                f"A {provider} subject is a UUID (the token's 'sub' claim); "
                f"{value!r} is not one. Refusing to bind an identity that cannot authenticate."
            ) from exc
    return value


def _user_id(value: str, *, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ProvisioningError(f"{label} must be a UUID; got {value!r}.") from exc


def resolve_target(
    session: Session,
    *,
    user_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    membership_id: uuid.UUID | None,
) -> User:
    """Find the user the operator named, without ever creating one.

    Exactly one selector must be given. Creating a user or a membership here would
    turn a binding tool into a provisioning backdoor, so a miss is an error.
    """
    selectors = [value for value in (user_id, actor_id, membership_id) if value is not None]
    if len(selectors) != 1:
        raise ProvisioningError("Name exactly one target: --user, --demo-actor or --membership.")

    if user_id is not None:
        user = session.get(User, user_id, with_for_update=True)
        if user is None:
            raise ProvisioningError(f"No user with id {user_id}. This tool never creates users.")
        return user

    if actor_id is not None:
        # A demo actor is a *user*, never a role: the demo header carries an id and
        # the backend loads roles from the database, which is exactly the shape of
        # a real token subject.
        user = session.execute(
            select(User)
            .where(User.auth_provider == "demo", User.external_subject == str(actor_id))
            .with_for_update()
        ).scalar_one_or_none()
        if user is None:
            # A seeded demo actor's subject *is* its user id, and binding it replaces
            # that mapping - so after the first successful link this lookup no longer
            # matches. Falling back to the primary key keeps the documented command
            # idempotent instead of failing with "no demo actor" the second time it is
            # run, which read as though the binding had been lost.
            user = session.get(User, actor_id, with_for_update=True)
        if user is None:
            raise ProvisioningError(
                f"No demo actor and no user with id {actor_id}. Seed the demo dataset "
                "first (python scripts/dev_seed.py), then use the actor id it prints."
            )
        return user

    membership = session.get(OrganizationMembership, membership_id)
    if membership is None:
        raise ProvisioningError(
            f"No membership with id {membership_id}. This tool never creates memberships."
        )
    user = session.get(User, membership.user_id, with_for_update=True)
    if user is None:  # pragma: no cover - the FK makes this unreachable
        raise ProvisioningError(f"Membership {membership_id} references a missing user.")
    return user


def summarise(session: Session, user: User) -> TargetSummary:
    memberships = list(
        session.execute(
            select(OrganizationMembership)
            .where(OrganizationMembership.user_id == user.id)
            .order_by(OrganizationMembership.created_at)
        ).scalars()
    )
    roles = (
        list(
            session.execute(
                select(RoleAssignment.role).where(
                    RoleAssignment.membership_id.in_([m.id for m in memberships]),
                    RoleAssignment.revoked_at.is_(None),
                )
            ).scalars()
        )
        if memberships
        else []
    )
    return TargetSummary(user=user, memberships=memberships, roles=roles)


def link_identity(
    session: Session,
    *,
    user: User,
    subject: str,
    provider: str,
    rebind: bool = False,
    reason: str | None = None,
) -> LinkResult:
    """Bind (provider, subject) to ``user`` and append an audit event.

    The caller's transaction is the unit of atomicity: the mapping and its audit
    event are committed together or not at all.
    """
    before = IdentityMapping(user.auth_provider, user.external_subject)
    if before.is_bound and (before.provider, before.subject) == (provider, subject):
        return LinkResult(
            user_id=user.id,
            organization_id=user.primary_organization_id,
            before=before,
            after=before,
            changed=False,
        )

    summary = summarise(session, user)
    if not user.is_active:
        raise ProvisioningError(
            f"User {user.id} is deactivated. Reactivate the person before binding an identity; "
            "an identity bound to a deactivated user can only ever be refused."
        )
    if not summary.active_memberships:
        raise ProvisioningError(
            f"User {user.id} has no active membership, so every request would be 403. "
            "Fix the membership first - this tool will not invent one."
        )
    # A demo mapping is a development placeholder, not a real identity: replacing it
    # with a provider identity is the intended migration path, so it does not require
    # --rebind. It is still printed in the plan, still needs --confirm, and is still
    # recorded in the audit event, so it cannot happen unnoticed.
    replaces_placeholder = before.is_bound and before.provider == "demo"
    if before.is_bound and not replaces_placeholder and not rebind:
        raise ProvisioningError(
            f"User {user.id} is already bound to {before.describe()}. "
            "Pass --rebind to replace that mapping."
        )

    holder = session.execute(
        select(User)
        .where(User.auth_provider == provider, User.external_subject == subject)
        .with_for_update()
    ).scalar_one_or_none()
    if holder is not None and holder.id != user.id and not rebind:
        raise ProvisioningError(
            f"Subject {subject} is already bound to user {holder.id}. "
            "Pass --rebind to move it, which clears the previous holder in the same transaction."
        )

    transferred_from = None
    if holder is not None and holder.id != user.id:
        transferred_from = holder.id
        # Clear the previous holder first: the (auth_provider, external_subject)
        # uniqueness constraint would otherwise reject the transfer, and leaving
        # both rows bound is not a state this system defines.
        holder.auth_provider = None
        holder.external_subject = None
        session.flush()

    user.auth_provider = provider
    user.external_subject = subject
    session.flush()

    audit(
        session,
        action="identity.rebound"
        if (before.is_bound and not replaces_placeholder)
        else "identity.bound",
        entity_type="user",
        entity_id=user.id,
        organization_id=user.primary_organization_id,
        actor_type=AuditActorType.SYSTEM,
        actor_label=ACTOR_LABEL,
        before={
            "auth_provider": before.provider,
            "external_subject": before.subject,
        },
        after={
            "auth_provider": provider,
            "external_subject": subject,
            "transferred_from_user_id": str(transferred_from) if transferred_from else None,
        },
        reason=reason or "operator provisioned an external identity",
    )
    return LinkResult(
        user_id=user.id,
        organization_id=user.primary_organization_id,
        before=before,
        after=IdentityMapping(provider, subject),
        changed=True,
        transferred_from_user_id=transferred_from,
    )


def unlink_identity(session: Session, *, user: User, reason: str | None = None) -> LinkResult:
    """Remove a user's external identity, leaving them unable to authenticate.

    Reversing a binding must land in the safe state. Deleting the user would
    destroy claim history and audit trails, and repointing the identity at someone
    else silently transfers access, so the mapping is cleared instead: the person
    keeps their record and loses the ability to sign in with a provider identity.

    This does not - and cannot - revoke demo-mode access. Under
    ``AUTH_PROVIDER=demo`` the header carries a seeded user's id and the actor
    resolver falls back to a primary-key lookup, which is exactly what makes seeded
    demo identities work. Demo mode is for impersonation by design and is refused
    outside development; with a real provider selected the demo header authenticates
    nothing at all.
    """
    before = IdentityMapping(user.auth_provider, user.external_subject)
    if not before.is_bound:
        return LinkResult(
            user_id=user.id,
            organization_id=user.primary_organization_id,
            before=before,
            after=before,
            changed=False,
        )

    user.auth_provider = None
    user.external_subject = None
    session.flush()

    audit(
        session,
        action="identity.unbound",
        entity_type="user",
        entity_id=user.id,
        organization_id=user.primary_organization_id,
        actor_type=AuditActorType.SYSTEM,
        actor_label=ACTOR_LABEL,
        before={"auth_provider": before.provider, "external_subject": before.subject},
        after={"auth_provider": None, "external_subject": None},
        reason=reason or "operator revoked an external identity",
    )
    return LinkResult(
        user_id=user.id,
        organization_id=user.primary_organization_id,
        before=before,
        after=IdentityMapping(None, None),
        changed=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.provision_identity",
        description=(
            "Bind an external identity subject (for example a Supabase 'sub') to a "
            "user that already exists. Writes nothing without --confirm."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_target(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--user", help="target user UUID")
        sub.add_argument(
            "--demo-actor",
            dest="demo_actor",
            help="target the seeded demo actor with this id (the X-Demo-Actor-Id value)",
        )
        sub.add_argument("--membership", help="target the user owning this membership UUID")

    show = subparsers.add_parser("show", help="print a user's identity, memberships and roles")
    add_target(show)

    link = subparsers.add_parser("link", help="bind an external identity subject to a user")
    add_target(link)
    link.add_argument("--subject", required=True, help="the provider's subject identifier")
    link.add_argument(
        "--provider", default="supabase", help="identity provider (default: supabase)"
    )
    link.add_argument(
        "--rebind",
        action="store_true",
        help="replace an existing mapping or move a subject away from another user",
    )
    link.add_argument(
        "--reason", help="why this change is being made (recorded in the audit event)"
    )
    link.add_argument("--confirm", action="store_true", help="actually perform the write")
    link.add_argument("--dry-run", action="store_true", help="show the change without writing")

    unlink = subparsers.add_parser("unlink", help="remove a user's external identity")
    add_target(unlink)
    unlink.add_argument("--reason", help="recorded in the audit event")
    unlink.add_argument("--confirm", action="store_true", help="actually perform the write")
    unlink.add_argument("--dry-run", action="store_true", help="show the change without writing")
    return parser


def _do_write(args: argparse.Namespace) -> bool:
    """Whether this invocation was instructed to write."""
    return bool(args.confirm) and not bool(args.dry_run)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _build_parser().parse_args(argv)
    user_id = _user_id(args.user, label="--user") if args.user else None
    actor_id = _user_id(args.demo_actor, label="--demo-actor") if args.demo_actor else None
    membership_id = _user_id(args.membership, label="--membership") if args.membership else None

    try:
        if args.command == "show":
            with session_scope() as session:
                user = resolve_target(
                    session, user_id=user_id, actor_id=actor_id, membership_id=membership_id
                )
                print(summarise(session, user).describe())
            return EXIT_OK

        if args.command == "link":
            provider = validate_provider(args.provider)
            subject = validate_subject(args.subject, provider=provider)
            with session_scope() as session:
                user = resolve_target(
                    session, user_id=user_id, actor_id=actor_id, membership_id=membership_id
                )
                summary = summarise(session, user)
                before = IdentityMapping(user.auth_provider, user.external_subject)
                print(summary.describe())
                print()
                print(f"intended change: {before.describe()}\n            ->  {provider}:{subject}")
                if not _do_write(args):
                    # No rollback here: nothing has been written, and the caller's
                    # transaction may hold work from elsewhere in the process.
                    print(
                        "\nNothing was written. Re-run with --confirm to apply.",
                        file=sys.stderr,
                    )
                    return EXIT_NOT_CONFIRMED
                result = link_identity(
                    session,
                    user=user,
                    subject=subject,
                    provider=provider,
                    rebind=bool(args.rebind),
                    reason=args.reason,
                )
            print()
            if not result.changed:
                print(f"Already bound to {result.after.describe()}. No change, no new audit event.")
            else:
                print(f"Bound {result.user_id} to {result.after.describe()}.")
                if result.transferred_from_user_id:
                    print(
                        f"Subject moved from user {result.transferred_from_user_id}, "
                        "whose identity is now cleared."
                    )
                print("Audit event appended in the same transaction.")
            return EXIT_OK

        # unlink
        with session_scope() as session:
            user = resolve_target(
                session, user_id=user_id, actor_id=actor_id, membership_id=membership_id
            )
            print(summarise(session, user).describe())
            before = IdentityMapping(user.auth_provider, user.external_subject)
            print()
            print(
                f"intended change: {before.describe()}\n            ->  no external identity bound"
            )
            if not _do_write(args):
                print("\nNothing was written. Re-run with --confirm to apply.", file=sys.stderr)
                return EXIT_NOT_CONFIRMED
            result = unlink_identity(session, user=user, reason=args.reason)
        print()
        if not result.changed:
            print("No external identity was bound. No change, no new audit event.")
        else:
            print(f"Cleared the identity of {result.user_id}.")
            print("The user, their memberships and their claim history are untouched.")
            print(
                "With a real provider that user can no longer authenticate. Under "
                "AUTH_PROVIDER=demo the header still resolves a seeded actor by user id, "
                "which is demo mode's documented behaviour and cannot be revoked here."
            )
        return EXIT_OK
    except ProvisioningError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except IntegrityError as exc:
        print(
            "Refused: the database rejected this mapping, so an identity is still bound "
            f"elsewhere or the subject is not unique ({exc.orig.__class__.__name__}). "
            "Nothing was written.",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    except SQLAlchemyError as exc:
        print(
            f"Failed: the database could not be reached or the transaction failed "
            f"({exc.__class__.__name__}). Nothing was written.",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    finally:
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
