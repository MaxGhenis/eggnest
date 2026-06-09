"""Tests for the core US household resources engine envelope."""

from fastapi.testclient import TestClient

from eggnest.core.router import run_core_scenario
from eggnest.core.us_household_resources import (
    OUTPUT_KEY,
    build_us_household_resources_scenario,
    extract_us_household_resources_result,
)
from eggnest.models import HouseholdInput, PersonInput
from main import app

client = TestClient(app)


def small_household_input() -> HouseholdInput:
    return HouseholdInput(
        state="CA",
        year=2025,
        people=[
            PersonInput(age=35, employment_income=40_000, is_tax_unit_head=True),
            PersonInput(age=6, is_tax_unit_dependent=True),
        ],
    )


def test_core_us_household_resources_returns_versioned_envelope():
    scenario = build_us_household_resources_scenario(
        small_household_input(), tags={"fixture": "small-household"}
    )

    result = run_core_scenario(scenario)
    household_result = extract_us_household_resources_result(result)

    assert result.schema_version == "eggnest.result.v1"
    assert result.scenario_schema_version == "eggnest.scenario.v1"
    assert result.engine == "us_household_resources"
    assert result.country == "USA"
    assert OUTPUT_KEY in result.outputs
    assert result.reproducibility.parameter_year == 2025
    assert "policyengine-us" in result.reproducibility.tax_engine_versions
    assert result.assumptions["currency"] == "USD"
    assert result.assumptions["state"] == "CA"
    assert any("not financial" in caveat for caveat in result.caveats)
    assert any(citation.id == "us:statutes/26/24" for citation in result.citations)
    assert any(
        citation.id == "us:statutes/26/24"
        for citation in household_result.output_citations["benefits.child_tax_credit"]
    )
    assert household_result.total_income == 40_000
    assert household_result.net_income == (
        household_result.total_income
        - household_result.total_taxes
        + household_result.total_benefits
    )


def test_core_simulate_endpoint_returns_household_envelope():
    scenario = build_us_household_resources_scenario(small_household_input())

    response = client.post("/core/simulate", json=scenario.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["engine"] == "us_household_resources"
    assert data["country"] == "USA"
    assert OUTPUT_KEY in data["outputs"]
    assert any(citation["id"] == "us:statutes/26/24" for citation in data["citations"])
    assert data["outputs"][OUTPUT_KEY]["total_income"] == 40_000
    assert "output_citations" in data["outputs"][OUTPUT_KEY]
