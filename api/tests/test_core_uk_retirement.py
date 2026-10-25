"""Tests for the core UK retirement engine envelope."""

from fastapi.testclient import TestClient

from eggnest.core.router import run_core_scenario
from eggnest.core.uk_retirement import (
    OUTPUT_KEY,
    build_uk_retirement_scenario,
    extract_uk_simulation_result,
)
from eggnest.models_uk import UKSimulationInput
from main import app

client = TestClient(app)


def small_uk_input() -> UKSimulationInput:
    return UKSimulationInput(
        current_age=65,
        max_age=65,
        annual_spending=10_000,
        isa_balance=100_000,
        sipp_balance=0,
        gia_balance=0,
        state_pension_annual=0,
        state_pension_start_age=67,
        n_simulations=100,
        random_seed=123,
        include_mortality=False,
    )


def test_core_uk_retirement_returns_versioned_envelope():
    scenario = build_uk_retirement_scenario(
        small_uk_input(), tags={"fixture": "small-uk"}
    )

    result = run_core_scenario(scenario)
    legacy_result = extract_uk_simulation_result(result)

    assert result.schema_version == "eggnest.result.v1"
    assert result.scenario_schema_version == "eggnest.scenario.v1"
    assert result.engine == "uk_retirement"
    assert result.country == "GBR"
    assert OUTPUT_KEY in result.outputs
    assert result.reproducibility.random_seed == 123
    assert "policyengine-uk-compiled" in result.reproducibility.tax_engine_versions
    assert result.assumptions["currency"] == "GBP"
    assert any("not financial" in caveat for caveat in result.caveats)
    assert legacy_result.success_rate == legacy_result.strict_horizon_success_rate


def test_core_simulate_endpoint_returns_envelope():
    scenario = build_uk_retirement_scenario(small_uk_input())

    response = client.post("/core/simulate", json=scenario.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["engine"] == "uk_retirement"
    assert data["country"] == "GBR"
    assert OUTPUT_KEY in data["outputs"]
    assert data["outputs"][OUTPUT_KEY]["metadata"]["n_simulations"] == 100
