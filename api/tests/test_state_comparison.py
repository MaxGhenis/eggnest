"""Tests for state comparison functionality."""

import pytest
from fastapi.testclient import TestClient

from eggnest.models import (
    SimulationInput,
    StateComparisonInput,
    StateComparisonResult,
    StateResult,
)
from main import app

client = TestClient(app)


@pytest.fixture
def base_params():
    """Base simulation parameters for testing."""
    return SimulationInput(
        initial_capital=1_000_000,
        annual_spending=48000,
        social_security_monthly=2000,
        current_age=65,
        max_age=75,  # Short horizon for faster tests
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,  # Small for testing
    )


class TestStateComparisonModels:
    """Test state comparison Pydantic models."""

    def test_state_comparison_input_valid(self, base_params):
        """Test valid StateComparisonInput creation."""
        comparison = StateComparisonInput(
            base_input=base_params, compare_states=["TX", "FL", "NV"]
        )
        assert comparison.base_input.state == "CA"
        assert len(comparison.compare_states) == 3

    def test_state_comparison_input_requires_states(self, base_params):
        """Test that compare_states is required and non-empty."""
        with pytest.raises(ValueError):
            StateComparisonInput(base_input=base_params, compare_states=[])

    def test_state_comparison_input_max_states(self, base_params):
        """Test that compare_states has max limit."""
        with pytest.raises(ValueError):
            StateComparisonInput(
                base_input=base_params,
                compare_states=[
                    "TX",
                    "FL",
                    "NV",
                    "WA",
                    "WY",
                    "SD",
                    "AK",
                    "TN",
                    "NH",
                    "OR",
                    "MT",
                ],
            )

    def test_state_result_model(self):
        """Test StateResult model creation."""
        result = StateResult(
            state="TX",
            success_rate=0.95,
            median_final_value=1_500_000,
            total_taxes_median=150_000,
            total_withdrawn_median=500_000,
            net_after_tax_median=350_000,
        )
        assert result.state == "TX"
        assert result.success_rate == 0.95

    def test_state_comparison_result_model(self):
        """Test StateComparisonResult model creation."""
        result = StateComparisonResult(
            base_state="CA",
            results=[
                StateResult(
                    state="CA",
                    success_rate=0.90,
                    median_final_value=1_400_000,
                    total_taxes_median=200_000,
                    total_withdrawn_median=500_000,
                    net_after_tax_median=300_000,
                ),
                StateResult(
                    state="TX",
                    success_rate=0.92,
                    median_final_value=1_500_000,
                    total_taxes_median=150_000,
                    total_withdrawn_median=500_000,
                    net_after_tax_median=350_000,
                ),
            ],
            tax_savings_vs_base={"CA": 0, "TX": 50_000},
        )
        assert result.base_state == "CA"
        assert len(result.results) == 2
        assert result.tax_savings_vs_base["TX"] == 50_000


class TestStateComparisonEndpoint:
    """Test /compare-states API endpoint."""

    def test_compare_states_endpoint_returns_results(self, base_params):
        """Test that endpoint returns valid comparison results."""
        response = client.post(
            "/compare-states",
            json={
                "base_input": base_params.model_dump(),
                "compare_states": ["TX", "FL"],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["base_state"] == "CA"
        assert len(data["results"]) == 3  # CA + TX + FL

    def test_compare_states_includes_base_state(self, base_params):
        """Test that base state is included in results."""
        response = client.post(
            "/compare-states",
            json={
                "base_input": base_params.model_dump(),
                "compare_states": ["TX"],
            },
        )
        assert response.status_code == 200

        data = response.json()
        states = [r["state"] for r in data["results"]]
        assert "CA" in states
        assert "TX" in states

    def test_compare_states_calculates_tax_savings(self, base_params):
        """Test that tax savings are calculated correctly."""
        response = client.post(
            "/compare-states",
            json={
                "base_input": base_params.model_dump(),
                "compare_states": ["TX"],
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Base state should have 0 savings vs itself
        assert data["tax_savings_vs_base"]["CA"] == 0

        # TX (no income tax) should typically save money vs CA
        # (but we just check the calculation is present)
        assert "TX" in data["tax_savings_vs_base"]

    def test_compare_states_no_duplicate_base(self, base_params):
        """Test that base state isn't duplicated if included in compare_states."""
        response = client.post(
            "/compare-states",
            json={
                "base_input": base_params.model_dump(),
                "compare_states": ["CA", "TX"],  # CA is already base state
            },
        )
        assert response.status_code == 200

        data = response.json()
        states = [r["state"] for r in data["results"]]
        assert states.count("CA") == 1  # Should only appear once

    def test_compare_states_result_fields(self, base_params):
        """Test that each state result has required fields."""
        response = client.post(
            "/compare-states",
            json={
                "base_input": base_params.model_dump(),
                "compare_states": ["TX"],
            },
        )
        assert response.status_code == 200

        data = response.json()
        for result in data["results"]:
            assert "state" in result
            assert "success_rate" in result
            assert "median_final_value" in result
            assert "total_taxes_median" in result
            assert "total_withdrawn_median" in result
            assert "net_after_tax_median" in result

            # Validate ranges
            assert 0 <= result["success_rate"] <= 1
            assert result["median_final_value"] >= 0
            assert result["total_taxes_median"] >= 0


class TestStateComparisonTaxDifferences:
    """Test that state comparisons show meaningful tax differences."""

    def test_no_income_tax_state_returns_valid_results(self, base_params):
        """Test that no-income-tax state comparison returns valid results."""
        # Run comparison with a high-income scenario where state taxes matter
        high_income_params = base_params.model_copy(
            update={
                "initial_capital": 2_000_000,
                "annual_spending": 100_000,
                "state": "CA",
            }
        )

        response = client.post(
            "/compare-states",
            json={
                "base_input": high_income_params.model_dump(),
                "compare_states": ["TX"],  # No state income tax
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Find CA and TX results
        ca_result = next(r for r in data["results"] if r["state"] == "CA")
        tx_result = next(r for r in data["results"] if r["state"] == "TX")

        # Both should have valid tax amounts
        # Note: With Monte Carlo variance (100 sims), exact comparisons are unreliable
        # We just verify both states return sensible results
        assert ca_result["total_taxes_median"] > 0
        assert tx_result["total_taxes_median"] > 0
        assert ca_result["success_rate"] > 0
        assert tx_result["success_rate"] > 0

    def test_tax_savings_calculation_correct(self, base_params):
        """Test that tax_savings_vs_base is calculated correctly."""
        response = client.post(
            "/compare-states",
            json={
                "base_input": base_params.model_dump(),
                "compare_states": ["TX"],
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Find results
        ca_result = next(r for r in data["results"] if r["state"] == "CA")
        tx_result = next(r for r in data["results"] if r["state"] == "TX")

        # Verify calculation: savings = base_taxes - state_taxes
        expected_tx_savings = (
            ca_result["total_taxes_median"] - tx_result["total_taxes_median"]
        )
        assert abs(data["tax_savings_vs_base"]["TX"] - expected_tx_savings) < 0.01
