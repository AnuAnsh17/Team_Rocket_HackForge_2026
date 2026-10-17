"""Roles, permissions and the explicit role -> permission map.

Design rules encoded here:

1. A privileged-sounding role name grants nothing on its own. Every capability
   is an explicit permission, and every role's permission set is enumerated
   below rather than derived from a hierarchy. There is deliberately no
   "admin implies everything" shortcut: ORG_ADMIN cannot decide expenses, and
   FINANCE_REVIEWER cannot manage memberships.
2. Permission checks are the coarse gate. They are necessary but NOT sufficient:
   resource-level scope (which organization, which employee, which department,
   which queue) is enforced separately by the scope resolvers in
   app/services/scope_service.py. Both must pass.
3. Nothing here is a policy rule. Permissions control *who may act*; the
   deterministic policy engine controls *whether a claim is compliant*.

The full matrix is documented in docs/authorization-matrix.md.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.enums import RoleCode


class Permission(StrEnum):
    """Atomic capabilities. Values are stable identifiers."""

    # --- Own records (every employee) -----------------------------------
    EXPENSE_CREATE_OWN = "expense:create_own"
    EXPENSE_READ_OWN = "expense:read_own"
    EXPENSE_UPDATE_OWN = "expense:update_own"
    EXPENSE_SUBMIT_OWN = "expense:submit_own"
    EXPENSE_WITHDRAW_OWN = "expense:withdraw_own"
    RECEIPT_UPLOAD_OWN = "receipt:upload_own"
    RECEIPT_READ_OWN = "receipt:read_own"
    RECEIPT_REEXTRACT_OWN = "receipt:reextract_own"
    PROFILE_READ_OWN = "profile:read_own"
    ALLOWANCE_READ_OWN = "allowance:read_own"

    # --- Scoped read across other employees ------------------------------
    EXPENSE_READ_TEAM = "expense:read_team"
    EXPENSE_READ_ORG_SCOPED = "expense:read_org_scoped"
    RECEIPT_READ_SCOPED = "receipt:read_scoped"
    PROFILE_READ_SCOPED = "profile:read_scoped"

    # --- Approval / review ------------------------------------------------
    EXPENSE_DECIDE_SCOPED = "expense:decide_scoped"
    FINDING_READ = "finding:read"
    FINDING_RESOLVE = "finding:resolve"
    DUPLICATE_READ = "duplicate:read"
    DUPLICATE_RESOLVE = "duplicate:resolve"
    APPROVAL_TASK_READ = "approval_task:read"
    APPROVAL_TASK_DECIDE = "approval_task:decide"

    # --- HR -----------------------------------------------------------------
    HR_REVIEW = "hr:review"
    HR_PROFILE_MANAGE = "hr:profile:manage"

    # --- Finance / analytics / audit ----------------------------------------
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_READ_ORG = "analytics:read_org"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    REVIEW_QUEUE_MANAGE = "review_queue:manage"

    # --- Policy and allowance administration --------------------------------
    POLICY_READ = "policy:read"
    POLICY_MANAGE = "policy:manage"
    POLICY_ASSIGNMENT_MANAGE = "policy_assignment:manage"
    ALLOWANCE_MANAGE = "allowance:manage"

    # --- Organization administration ----------------------------------------
    ORG_READ = "org:read"
    ORG_MANAGE = "org:manage"
    MEMBERSHIP_READ = "membership:read"
    MEMBERSHIP_MANAGE = "membership:manage"
    ROLE_MANAGE = "role:manage"

    # --- Demo-only ----------------------------------------------------------
    DEMO_SEED_RESET = "demo:seed_reset"


_EMPLOYEE_SELF: frozenset[Permission] = frozenset(
    {
        Permission.EXPENSE_CREATE_OWN,
        Permission.EXPENSE_READ_OWN,
        Permission.EXPENSE_UPDATE_OWN,
        Permission.EXPENSE_SUBMIT_OWN,
        Permission.EXPENSE_WITHDRAW_OWN,
        Permission.RECEIPT_UPLOAD_OWN,
        Permission.RECEIPT_READ_OWN,
        Permission.RECEIPT_REEXTRACT_OWN,
        Permission.PROFILE_READ_OWN,
        Permission.ALLOWANCE_READ_OWN,
    }
)

ROLE_PERMISSIONS: dict[RoleCode, frozenset[Permission]] = {
    # An employee may act only on their own records. Note the absence of any
    # scoped-read permission: an employee cannot read a colleague's claim.
    RoleCode.EMPLOYEE: _EMPLOYEE_SELF,
    # A manager may additionally read and decide on claims scoped to their
    # explicit direct-report relationships. The relationship is checked by the
    # scope resolver, not by this map.
    RoleCode.MANAGER: _EMPLOYEE_SELF
    | frozenset(
        {
            Permission.EXPENSE_READ_TEAM,
            Permission.RECEIPT_READ_SCOPED,
            Permission.PROFILE_READ_SCOPED,
            Permission.EXPENSE_DECIDE_SCOPED,
            Permission.FINDING_READ,
            Permission.APPROVAL_TASK_READ,
            Permission.APPROVAL_TASK_DECIDE,
        }
    ),
    # HR sees employment/profile context where authorized and handles HR
    # approval tasks. HR deliberately cannot resolve finance findings or
    # confirm duplicates.
    RoleCode.HR_REVIEWER: _EMPLOYEE_SELF
    | frozenset(
        {
            Permission.PROFILE_READ_SCOPED,
            Permission.EXPENSE_READ_ORG_SCOPED,
            Permission.HR_REVIEW,
            Permission.MEMBERSHIP_READ,
            Permission.APPROVAL_TASK_READ,
            Permission.APPROVAL_TASK_DECIDE,
            Permission.POLICY_READ,
        }
    ),
    # Finance review: receipt verification, findings, duplicates, decisions.
    RoleCode.FINANCE_REVIEWER: _EMPLOYEE_SELF
    | frozenset(
        {
            Permission.EXPENSE_READ_ORG_SCOPED,
            Permission.RECEIPT_READ_SCOPED,
            Permission.PROFILE_READ_SCOPED,
            Permission.EXPENSE_DECIDE_SCOPED,
            Permission.FINDING_READ,
            Permission.FINDING_RESOLVE,
            Permission.DUPLICATE_READ,
            Permission.DUPLICATE_RESOLVE,
            Permission.APPROVAL_TASK_READ,
            Permission.APPROVAL_TASK_DECIDE,
            Permission.POLICY_READ,
            Permission.ANALYTICS_READ,
            Permission.AUDIT_READ,
        }
    ),
    # Finance administration: review queues, reporting, authorized exports.
    RoleCode.FINANCE_ADMIN: _EMPLOYEE_SELF
    | frozenset(
        {
            Permission.EXPENSE_READ_ORG_SCOPED,
            Permission.RECEIPT_READ_SCOPED,
            Permission.PROFILE_READ_SCOPED,
            Permission.EXPENSE_DECIDE_SCOPED,
            Permission.FINDING_READ,
            Permission.FINDING_RESOLVE,
            Permission.DUPLICATE_READ,
            Permission.DUPLICATE_RESOLVE,
            Permission.APPROVAL_TASK_READ,
            Permission.APPROVAL_TASK_DECIDE,
            Permission.REVIEW_QUEUE_MANAGE,
            Permission.POLICY_READ,
            Permission.ANALYTICS_READ,
            Permission.ANALYTICS_READ_ORG,
            Permission.AUDIT_READ,
            Permission.AUDIT_EXPORT,
        }
    ),
    # Organization administration: memberships, roles, org configuration.
    # Explicitly NO expense decision, finding resolution, or audit export.
    RoleCode.ORG_ADMIN: _EMPLOYEE_SELF
    | frozenset(
        {
            Permission.ORG_READ,
            Permission.ORG_MANAGE,
            Permission.MEMBERSHIP_READ,
            Permission.MEMBERSHIP_MANAGE,
            Permission.ROLE_MANAGE,
            Permission.PROFILE_READ_SCOPED,
            Permission.POLICY_READ,
            Permission.POLICY_ASSIGNMENT_MANAGE,
            Permission.ALLOWANCE_MANAGE,
            Permission.AUDIT_READ,
        }
    ),
    # Policy administration: policy and allowance artefacts only.
    # Explicitly NO people administration and NO expense decisions.
    RoleCode.POLICY_ADMIN: _EMPLOYEE_SELF
    | frozenset(
        {
            Permission.POLICY_READ,
            Permission.POLICY_MANAGE,
            Permission.POLICY_ASSIGNMENT_MANAGE,
            Permission.ALLOWANCE_MANAGE,
            Permission.ORG_READ,
            Permission.AUDIT_READ,
        }
    ),
    # Auditor: read-only. No mutation permission of any kind.
    RoleCode.AUDITOR: frozenset(
        {
            Permission.AUDIT_READ,
            Permission.AUDIT_EXPORT,
            Permission.ANALYTICS_READ,
            Permission.ANALYTICS_READ_ORG,
            Permission.EXPENSE_READ_ORG_SCOPED,
            Permission.FINDING_READ,
            Permission.DUPLICATE_READ,
            Permission.POLICY_READ,
        }
    ),
    # Internal service identity. Used by scheduled re-evaluation only.
    RoleCode.SERVICE: frozenset({Permission.FINDING_READ, Permission.EXPENSE_READ_ORG_SCOPED}),
}

# Demo identities may seed and reset synthetic data. Never granted in
# production because DEMO_MODE is refused there by config validation.
for _role in (RoleCode.ORG_ADMIN, RoleCode.FINANCE_ADMIN):
    ROLE_PERMISSIONS[_role] = ROLE_PERMISSIONS[_role] | {Permission.DEMO_SEED_RESET}


def permissions_for_roles(roles: frozenset[RoleCode] | set[RoleCode]) -> frozenset[Permission]:
    """Union of the permissions of every role held. Never expands to all."""
    granted: set[Permission] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(granted)


def role_permission_map() -> dict[str, list[str]]:
    """Serialisable view of the matrix, used by the authorization docs test."""
    return {
        role.value: sorted(perm.value for perm in sorted(ROLE_PERMISSIONS.get(role, frozenset())))
        for role in RoleCode
    }
