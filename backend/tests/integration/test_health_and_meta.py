"""Health and metadata endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.meta_service import CONTRACT_VERSION
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestHealth:
    def test_health_returns_ok_with_a_reachable_database(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in {"ok", "degraded"}
        assert body["components"]["database"]["status"] == "ok"
        assert body["api_version"] == "v1"
        assert body["demo_mode"] is True

    def test_health_names_the_absent_capabilities_rather_than_claiming_ok(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/v1/health").json()
        assert body["components"]["extraction_provider"]["status"] == "not_configured"
        assert body["components"]["policy_engine"]["status"] == "not_configured"
        assert "no approved policy document" in body["components"]["policy_engine"]["detail"]

    def test_health_leaks_no_secrets(self, client: TestClient) -> None:
        raw = client.get("/api/v1/health").text.lower()
        for forbidden in (
            "password",
            "postgresql://",
            "proofline:proofline",
            "service_role",
            "secret",
        ):
            assert forbidden not in raw, f"health response must not contain {forbidden!r}"

    def test_health_requires_no_authentication(self, client: TestClient) -> None:
        """A load balancer must be able to probe it."""
        assert client.get("/api/v1/health").status_code == 200

    def test_request_id_is_echoed(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
        assert response.headers["x-request-id"] == "abc123"

    def test_a_hostile_request_id_is_replaced_not_echoed(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "x" * 500})
        assert response.headers["x-request-id"] != "x" * 500


class TestMeta:
    def test_enum_catalogue_exposes_the_canonical_values(self, client: TestClient) -> None:
        enums = client.get("/api/v1/meta/enums").json()["enums"]
        assert enums["RuleResult"] == ["PASS", "FAIL", "UNKNOWN"]
        assert enums["ReviewAction"] == ["approve", "reject", "request_correction", "escalate"]
        assert enums["RecommendedAction"] == ["none", "review", "request_correction", "escalate"]
        assert enums["FieldSource"] == [
            "receipt_extraction",
            "employee_input",
            "reviewer_correction",
            "imported_data",
            "computed",
        ]
        assert "withdrawn" in enums["ExpenseStatus"]

    def test_meta_reports_unimplemented_capabilities(self, client: TestClient) -> None:
        body = client.get("/api/v1/meta").json()
        assert body["contract_version"] == CONTRACT_VERSION
        # The reported label must match the reviewed document's own version line, so the
        # two cannot drift apart.
        contract_header = (
            Path(__file__).resolve().parents[3] / "docs" / "api-contract.md"
        ).read_text(encoding="utf-8")
        assert f"Contract version:** {CONTRACT_VERSION}" in contract_header
        assert body["implemented_endpoint_count"] >= 4
        joined = " ".join(body["unimplemented_capabilities"])
        for capability in (
            "receipt extraction",
            "production authentication",
            "policy rule execution",
        ):
            assert capability in joined

    def test_meta_reports_demo_mode_and_environment(self, client: TestClient) -> None:
        body = client.get("/api/v1/meta").json()
        assert body["environment"] == "test"
        assert body["demo_mode"] is True


class TestOpenApiServing:
    def test_openapi_is_served_inside_the_versioned_prefix(self, client: TestClient) -> None:
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert spec["info"]["title"] == "Proofline API"
        assert all(path.startswith("/api/v1/") for path in spec["paths"])

    def test_docs_are_reachable(self, client: TestClient) -> None:
        assert client.get("/docs").status_code == 200
