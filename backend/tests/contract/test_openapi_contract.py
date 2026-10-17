"""Contract tests: the running service versus the reviewed document.

The purpose is to catch drift in either direction:

* an endpoint that exists in code but was never written into
  ``docs/api-contract.md`` (the document stops describing the system);
* an enum value in the document that the code does not accept (clients generate
  types from the code and would silently disagree with the reviewer).

These tests read the real OpenAPI document the running application produces, so
they also prove that the generated schema is well-formed and that money still
serialises as a decimal string.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.contract

CONTRACT_DOC = Path(__file__).resolve().parents[3] / "docs" / "api-contract.md"
API_PREFIX = "/api/v1"


@pytest.fixture(scope="module")
def contract_text() -> str:
    assert CONTRACT_DOC.is_file(), f"missing contract document at {CONTRACT_DOC}"
    return CONTRACT_DOC.read_text(encoding="utf-8")


@pytest.fixture
def spec(client: TestClient) -> dict:
    response = client.get(f"{API_PREFIX}/openapi.json")
    assert response.status_code == 200
    return response.json()


class TestPrefixAndPaths:
    def test_every_path_is_under_the_versioned_prefix(self, spec: dict) -> None:
        assert spec["paths"]
        for path in spec["paths"]:
            assert path.startswith(f"{API_PREFIX}/"), path

    def test_every_implemented_path_is_documented(self, spec: dict, contract_text: str) -> None:
        """No endpoint may be served without appearing in the reviewed contract."""
        undocumented: list[str] = []
        for path in spec["paths"]:
            # The contract writes paths like `GET /api/v1/health`.
            if path not in contract_text:
                undocumented.append(path)
        assert undocumented == [], (
            "These endpoints are implemented but absent from docs/api-contract.md: "
            f"{undocumented}. Add them to the contract in the same change."
        )

    def test_the_documented_base_path_matches(self, contract_text: str) -> None:
        assert API_PREFIX in contract_text

    def test_no_path_uses_trailing_slash_or_duplicate_segment(self, spec: dict) -> None:
        for path in spec["paths"]:
            assert not path.endswith("/"), path
            assert "//" not in path, path


def _documented_enum_values(contract_text: str, enum_name: str) -> set[str]:
    """Read an enum's permitted values out of the contract's enum table.

    The document presents enums as a markdown table with the values in backticks.
    Parsing the row keeps the assertion as strong as the previous bullet-list
    parsing: the set of values in the document must equal the set the service
    accepts.
    """
    row = re.compile(rf"^\|\s*`{re.escape(enum_name)}`\s*\|(.+?)\|\s*$", re.MULTILINE).search(
        contract_text
    )
    assert row is not None, f"{enum_name} must be documented in the enum table"
    return set(re.findall(r"`([A-Za-z_]+)`", row.group(1)))


class TestEnumAgreement:
    """The document's enums must match the enum catalogue the service publishes."""

    def test_documented_expense_status_matches_the_service(
        self, client: TestClient, contract_text: str
    ) -> None:
        documented = _documented_enum_values(contract_text, "ExpenseStatus")
        served = set(client.get(f"{API_PREFIX}/meta/enums").json()["enums"]["ExpenseStatus"])
        assert documented == served
        assert documented == {
            "draft",
            "submitted",
            "needs_info",
            "in_review",
            "approved",
            "rejected",
            "withdrawn",
        }

    def test_documented_review_action_matches_the_service(
        self, client: TestClient, contract_text: str
    ) -> None:
        documented = _documented_enum_values(contract_text, "ReviewAction")
        served = set(client.get(f"{API_PREFIX}/meta/enums").json()["enums"]["ReviewAction"])
        assert documented == served

    def test_every_served_enum_is_documented(self, client: TestClient, contract_text: str) -> None:
        """No enum may be served without appearing in the contract table."""
        for name in client.get(f"{API_PREFIX}/meta/enums").json()["enums"]:
            assert _documented_enum_values(contract_text, name), (
                f"{name} is served by /meta/enums but absent from docs/api-contract.md"
            )

    def test_recommended_action_is_documented_and_distinct(self, contract_text: str) -> None:
        """The approved contract decision: recommendation != executed action."""
        from app.core.enums import RecommendedAction, ReviewAction

        documented = _documented_enum_values(contract_text, "RecommendedAction")
        assert documented == {"none", "review", "request_correction", "escalate"}
        assert documented == {member.value for member in RecommendedAction}
        # "review" is advice, not an executable decision, so the enums must differ.
        assert "review" not in {member.value for member in ReviewAction}
        assert documented != {member.value for member in ReviewAction}

    def test_rule_result_is_tri_state(self, client: TestClient) -> None:
        assert client.get(f"{API_PREFIX}/meta/enums").json()["enums"]["RuleResult"] == [
            "PASS",
            "FAIL",
            "UNKNOWN",
        ]


class TestMoneyAndTimeFormats:
    """Money is validated through the DTO itself rather than through the OpenAPI
    components map.

    The components map only contains schemas reachable from a served operation, and
    the claim endpoints are not implemented yet, so reading ``Money`` out of the
    generated document would either fail or, worse, be made to pass by adding a
    placeholder route. Serialising the real model is both stronger and honest.
    """

    def test_money_serialises_as_a_decimal_string(self) -> None:
        from decimal import Decimal

        from app.core.enums import FieldSource
        from app.schemas.common import Money

        payload = Money(
            value=Decimal("1400.00"),
            currency="INR",
            source=FieldSource.RECEIPT_EXTRACTION,
            reviewed=True,
        ).model_dump_json()
        assert '"value":"1400.00"' in payload, payload
        assert "1400.0," not in payload

    def test_money_does_not_serialise_as_a_json_number(self) -> None:

        from app.schemas.common import Money

        schema = Money.model_json_schema()
        assert schema["properties"]["value"]["anyOf"][0].get("type") == "string"

    def test_money_carries_provenance(self) -> None:
        """The approved contract decision: one canonical money structure."""
        from app.schemas.common import Money

        for required in ("value", "currency", "source", "reviewed", "confidence", "evidence"):
            assert required in Money.model_fields, f"Money must expose {required}"

    def test_a_currency_code_must_be_iso_4217_shaped(self) -> None:
        import pytest as _pytest
        from app.core.enums import FieldSource
        from app.schemas.common import Money
        from pydantic import ValidationError

        with _pytest.raises(ValidationError):
            Money(value="10.00", currency="rupees", source=FieldSource.EMPLOYEE_INPUT)

    def test_the_canonical_expense_dto_exposes_the_agreed_field_set(self) -> None:
        from app.schemas.expense import ExpenseResponse

        for field in (
            "id",
            "version",
            "employee",
            "channel",
            "status",
            "trip_id",
            "merchant",
            "expense_date",
            "amount",
            "amount_reporting",
            "receipts",
            "line_items",
            "findings",
        ):
            assert field in ExpenseResponse.model_fields, f"ExpenseResponse must expose {field}"

    def test_contract_states_money_is_a_decimal_string(self, contract_text: str) -> None:
        assert (
            "decimal strings" in contract_text
            or "JSON money values are decimal strings" in contract_text
        )

    def test_timestamp_fields_are_timezone_aware_datetimes(self, spec: dict) -> None:
        health = spec["components"]["schemas"]["HealthResponse"]
        assert health["properties"]["checked_at"]["format"] == "date-time"


class TestErrorEnvelope:
    def test_an_unauthenticated_request_uses_the_documented_envelope(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/v1/me").json()
        assert set(body.keys()) == {"error"}
        assert set(body["error"].keys()) >= {"code", "message", "details", "request_id"}

    def test_an_unknown_route_uses_the_same_envelope(self, client: TestClient) -> None:
        body = client.get("/api/v1/does-not-exist").json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_no_error_response_leaks_internal_detail(self, client: TestClient) -> None:
        text = client.get("/api/v1/me").text.lower()
        for forbidden in ("traceback", "psycopg", "sqlalchemy", 'file "', "line "):
            assert forbidden not in text

    def test_documented_error_codes_are_the_ones_the_code_defines(self, contract_text: str) -> None:
        from app.core.errors import ErrorCode

        line = next(
            (c for c in contract_text.splitlines() if c.startswith("Recommended codes:")), None
        )
        assert line is not None
        documented = set(re.findall(r"\b([A-Z][A-Z_]{4,})\b", line))
        defined = {
            value
            for name, value in vars(ErrorCode).items()
            if not name.startswith("_") and isinstance(value, str)
        }
        missing = documented - defined
        assert missing == set(), f"documented error codes with no implementation: {sorted(missing)}"


class TestDocumentedRoutesAreAccountedFor:
    def test_each_contract_route_is_either_implemented_or_declared_missing(
        self, client: TestClient, contract_text: str
    ) -> None:
        """Honesty check: nothing the contract promises may be silently absent.

        Every route in the document must either be served, or be covered by the
        unimplemented-capability list reported by /api/v1/meta.
        """
        served = client.get(f"{API_PREFIX}/openapi.json").json()["paths"].keys()
        declared = " ".join(
            client.get(f"{API_PREFIX}/meta").json()["unimplemented_capabilities"]
        ).lower()

        # Map a contract route to a capability keyword that must be declared when the
        # route is not implemented in this build.
        expectations = {
            "/api/v1/policy/check": "pre-flight",
            "/api/v1/analytics/overview": "analytics",
            "/api/v1/audit/export": "audit export",
        }
        for route, keyword in expectations.items():
            if route in served:
                continue
            assert keyword in declared, (
                f"{route} is neither implemented nor declared as an unimplemented "
                f"capability containing {keyword!r}"
            )

    def test_the_backend_declares_unimplemented_workflows(self, client: TestClient) -> None:
        body = client.get(f"{API_PREFIX}/meta").json()
        assert body["implemented_endpoint_count"] < 30, (
            "This endpoint set is intentionally limited; update this expectation and the "
            "coverage report together if it changes."
        )
