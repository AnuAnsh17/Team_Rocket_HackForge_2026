"""The authorization matrix.

These tests pin down the negative space, which is the part that matters: a
privileged-sounding role must not grant capabilities that were never assigned to
it.
"""

from __future__ import annotations

import pytest
from app.core.enums import RoleCode
from app.core.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    permissions_for_roles,
    role_permission_map,
)

pytestmark = pytest.mark.unit


class TestEmployeeScope:
    def test_employee_has_only_own_record_permissions(self) -> None:
        granted = ROLE_PERMISSIONS[RoleCode.EMPLOYEE]
        scoped = {permission for permission in granted if "scoped" in permission.value}
        assert scoped == set()

    def test_employee_cannot_read_another_employees_claims(self) -> None:
        granted = permissions_for_roles({RoleCode.EMPLOYEE})
        assert Permission.EXPENSE_READ_ORG_SCOPED not in granted
        assert Permission.EXPENSE_READ_TEAM not in granted

    def test_employee_cannot_decide_claims(self) -> None:
        assert Permission.EXPENSE_DECIDE_SCOPED not in permissions_for_roles({RoleCode.EMPLOYEE})


class TestPrivilegeSeparation:
    def test_org_admin_cannot_decide_expenses(self) -> None:
        granted = permissions_for_roles({RoleCode.ORG_ADMIN})
        assert Permission.EXPENSE_DECIDE_SCOPED not in granted
        assert Permission.FINDING_RESOLVE not in granted

    def test_org_admin_cannot_export_audit(self) -> None:
        assert Permission.AUDIT_EXPORT not in permissions_for_roles({RoleCode.ORG_ADMIN})

    def test_hr_reviewer_cannot_resolve_finance_findings(self) -> None:
        granted = permissions_for_roles({RoleCode.HR_REVIEWER})
        assert Permission.FINDING_RESOLVE not in granted
        assert Permission.DUPLICATE_RESOLVE not in granted

    def test_finance_reviewer_cannot_manage_memberships(self) -> None:
        granted = permissions_for_roles({RoleCode.FINANCE_REVIEWER})
        assert Permission.MEMBERSHIP_MANAGE not in granted
        assert Permission.ROLE_MANAGE not in granted

    def test_policy_admin_cannot_manage_people(self) -> None:
        granted = permissions_for_roles({RoleCode.POLICY_ADMIN})
        assert Permission.MEMBERSHIP_MANAGE not in granted
        assert Permission.ROLE_MANAGE not in granted
        assert Permission.EXPENSE_DECIDE_SCOPED not in granted

    def test_auditor_holds_no_mutation_permission(self) -> None:
        granted = ROLE_PERMISSIONS[RoleCode.AUDITOR]
        mutations = {
            Permission.EXPENSE_DECIDE_SCOPED,
            Permission.FINDING_RESOLVE,
            Permission.DUPLICATE_RESOLVE,
            Permission.MEMBERSHIP_MANAGE,
            Permission.POLICY_MANAGE,
            Permission.ROLE_MANAGE,
            Permission.EXPENSE_UPDATE_OWN,
        }
        assert granted & mutations == set()

    def test_no_role_is_all_permissions(self) -> None:
        every = set(Permission)
        for role in RoleCode:
            assert ROLE_PERMISSIONS[role] != every, f"{role.value} must not hold every permission"

    def test_every_role_has_at_least_one_permission_defined(self) -> None:
        for role in RoleCode:
            assert role in ROLE_PERMISSIONS


class TestPermissionComposition:
    def test_multiple_roles_union_their_permissions(self) -> None:
        combined = permissions_for_roles({RoleCode.EMPLOYEE, RoleCode.MANAGER})
        assert Permission.EXPENSE_READ_TEAM in combined
        assert Permission.EXPENSE_READ_OWN in combined

    def test_unknown_role_grants_nothing(self) -> None:
        assert permissions_for_roles(set()) == frozenset()

    def test_documented_matrix_is_serialisable(self) -> None:
        matrix = role_permission_map()
        assert "employee" in matrix
        assert all(isinstance(values, list) for values in matrix.values())
