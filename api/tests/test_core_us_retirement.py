"""Tests for the core US retirement engine envelope."""

from fastapi.testclient import TestClient

from eggnest.core.router import run_core_scenario
from eggnest.core.us_retirement import (
    OUTPUT_KEY,
    build_us_retirement_scenario,
    extract_us_simulation_result,
)
from eggnest.models import SimulationInput
from main import app

client = TestClient(app)


def small_us_input() -> SimulationInput:
    return SimulationInput(
        current_age=65,
        max_age=66,
        initial_capital=100_000,
        annual_spending=10_000,
        social_security_monthly=0,
        pension_annual=0,
        state="CA",
        filing_status="single",
        n_simulations=100,
        random_seed=123,
        include_mortality=False,
    )


def test_core_us_retirement_returns_versioned_envelope():
    scenario = build_us_retirement_scenario(
        small_us_input(), tags={"fixture": "small-us"}
    )

    result = run_core_scenario(scenario)
    legacy_result = extract_us_simulation_result(result)

    assert result.schema_version == "eggnest.result.v1"
    assert result.scenario_schema_version == "eggnest.scenario.v1"
    assert result.engine == "us_retirement"
    assert result.country == "USA"
    assert OUTPUT_KEY in result.outputs
    assert result.reproducibility.random_seed == 123
    assert result.reproducibility.parameter_year is not None
    assert "policyengine-us" in result.reproducibility.tax_engine_versions
    assert result.assumptions["currency"] == "USD"
    assert any("not financial" in caveat for caveat in result.caveats)
    assert legacy_result.success_rate == 1.0


def test_core_simulate_endpoint_returns_us_envelope():
    scenario = build_us_retirement_scenario(small_us_input())

    response = client.post("/core/simulate", json=scenario.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["engine"] == "us_retirement"
    assert data["country"] == "USA"
    assert OUTPUT_KEY in data["outputs"]
    assert data["outputs"][OUTPUT_KEY]["success_rate"] == 1.0


def test_legacy_simulate_endpoint_preserves_us_shape():
    response = client.post("/simulate", json=small_us_input().model_dump())

    assert response.status_code == 200
    data = response.json()
    assert "success_rate" in data
    assert "outputs" not in data
    assert data["success_rate"] == 1.0


def test_core_us_random_seed_repeats_paths():
    scenario = build_us_retirement_scenario(
        small_us_input().model_copy(update={"max_age": 66, "return_model": "normal"})
    )

    first = extract_us_simulation_result(run_core_scenario(scenario))
    second = extract_us_simulation_result(run_core_scenario(scenario))

    assert first.percentile_paths == second.percentile_paths
    assert first.percentiles == second.percentiles
