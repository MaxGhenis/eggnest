"""Tests for asset allocation comparison API endpoint."""

import pytest
from fastapi.testclient import TestClient

import main
from eggnest.models import (
    AllocationComparisonResult,
    AllocationInput,
    AllocationResult,
    SimulationInput,
)
from main import app

client = TestClient(app)


@pytest.fixture
def base_params():
    """Base simulation parameters for testing."""
    return SimulationInput(
        initial_capital=500_000,
        annual_spending=40_000,
        current_age=65,
        max_age=80,  # Keep comparison tests practical; explicit long-horizon cases override this
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,  # Small for faster tests
    )


@pytest.fixture
def stub_allocation_batch(monkeypatch):
    """Stub simulator summaries for allocation contract tests."""

    async def fake_batch(inputs):
        summaries = []
        for params in inputs:
            withdrawal_rate = params.annual_spending / max(params.total_capital, 1)
            stock_alloc = params.stock_allocation
            success_rate = min(
                0.99, max(0.05, 1.0 - withdrawal_rate * 3 + stock_alloc * 0.15)
            )
            median_final = params.total_capital * max(
                0.1, 1.0 + stock_alloc * 0.4 - withdrawal_rate * 4
            )
            summaries.append(
                {
                    "success_rate": success_rate,
                    "median_final_value": median_final,
                    "total_taxes_median": params.annual_spending * 0.1,
                    "total_withdrawn_median": params.annual_spending
                    * (params.max_age - params.current_age),
                    "percentiles": {
                        "p5": median_final * 0.5,
                        "p25": median_final * 0.8,
                        "p50": median_final,
                        "p75": median_final * 1.2,
                        "p95": median_final * 1.5,
                    },
                }
            )
        return summaries

    monkeypatch.setattr(main, "_run_simulation_batch", fake_batch)


class TestAllocationModels:
    """Test allocation Pydantic models."""

    def test_allocation_input_valid(self, base_params):
        """Test valid AllocationInput creation."""
        alloc_input = AllocationInput(
            base_input=base_params,
            allocations=[0.4, 0.6, 0.8, 1.0],
        )
        assert alloc_input.allocations == [0.4, 0.6, 0.8, 1.0]

    def test_allocation_input_default_allocations(self, base_params):
        """Test default allocations if not specified."""
        alloc_input = AllocationInput(
            base_input=base_params,
        )
        # Default should be common allocations like 40%, 60%, 80%, 100%
        assert len(alloc_input.allocations) >= 3

    def test_allocation_input_validates_range(self, base_params):
        """Test that allocations must be between 0 and 1."""
        with pytest.raises(ValueError):
            AllocationInput(
                base_input=base_params,
                allocations=[0.5, 1.5],  # 1.5 is invalid
            )

        with pytest.raises(ValueError):
            AllocationInput(
                base_input=base_params,
                allocations=[-0.1, 0.5],  # -0.1 is invalid
            )

    def test_allocation_result_model(self):
        """Test AllocationResult model creation."""
        result = AllocationResult(
            stock_allocation=0.6,
            bond_allocation=0.4,
            success_rate=0.92,
            median_final_value=450_000,
            percentile_5_final_value=100_000,
            percentile_95_final_value=900_000,
            volatility=0.10,
            expected_return=0.055,
        )
        assert result.stock_allocation == 0.6
        assert result.bond_allocation == 0.4

    def test_allocation_comparison_result_model(self):
        """Test AllocationComparisonResult model creation."""
        result = AllocationComparisonResult(
            results=[
                AllocationResult(
                    stock_allocation=1.0,
                    bond_allocation=0.0,
                    success_rate=0.85,
                    median_final_value=500_000,
                    percentile_5_final_value=50_000,
                    percentile_95_final_value=1_200_000,
                    volatility=0.16,
                    expected_return=0.07,
                ),
            ],
            highest_success_allocation=1.0,
            highest_safety_allocation=0.4,
            summary="",
        )
        assert result.highest_success_allocation == 1.0


class TestAllocationEndpoint:
    """Test /compare-allocations API endpoint."""

    @pytest.mark.montecarlo_smoke
    def test_compare_allocations_returns_results(self, base_params):
        """Test that endpoint returns valid comparison results."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
                "allocations": [0.4, 0.6, 1.0],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3

    def test_compare_allocations_default_allocations(
        self, base_params, stub_allocation_batch
    ):
        """Test comparison with default allocations."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) >= 3

    def test_compare_allocations_result_fields(
        self, base_params, stub_allocation_batch
    ):
        """Test that each result has required fields."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
                "allocations": [0.6],
            },
        )
        assert response.status_code == 200

        data = response.json()
        result = data["results"][0]

        # Required fields
        assert "stock_allocation" in result
        assert "bond_allocation" in result
        assert "success_rate" in result
        assert "median_final_value" in result
        assert "percentile_5_final_value" in result
        assert "percentile_95_final_value" in result

        # Validate sum to 1
        assert result["stock_allocation"] + result["bond_allocation"] == pytest.approx(
            1.0
        )

        # Validate ranges
        assert 0 <= result["success_rate"] <= 1
        assert result["stock_allocation"] == 0.6

    def test_compare_allocations_identifies_optimal(
        self, base_params, stub_allocation_batch
    ):
        """Test that optimal allocations are identified."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
                "allocations": [0.2, 0.4, 0.6, 0.8, 1.0],
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Should have summary allocations identified
        assert "highest_success_allocation" in data
        assert 0 <= data["highest_success_allocation"] <= 1

        assert "highest_safety_allocation" in data
        assert 0 <= data["highest_safety_allocation"] <= 1

    def test_compare_allocations_volatility_ordering(
        self, base_params, stub_allocation_batch
    ):
        """Test that higher stock allocations have higher volatility."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
                "allocations": [0.0, 0.5, 1.0],
            },
        )
        assert response.status_code == 200

        data = response.json()
        results = {r["stock_allocation"]: r for r in data["results"]}

        # Higher stock allocation should mean higher volatility
        # This tests the fundamental property of diversification
        if "volatility" in results[0.0]:
            assert results[0.0]["volatility"] <= results[0.5]["volatility"]
            assert results[0.5]["volatility"] <= results[1.0]["volatility"]


class TestAllocationWithDifferentScenarios:
    """Test allocations with different financial scenarios."""

    def test_conservative_investor_scenario(
        self, base_params, stub_allocation_batch
    ):
        """Test scenario for conservative investor (low spending rate)."""
        conservative_params = base_params.model_copy(
            update={
                "annual_spending": 20_000,  # 4% withdrawal rate
            }
        )

        response = client.post(
            "/compare-allocations",
            json={
                "base_input": conservative_params.model_dump(),
                "allocations": [0.3, 0.6, 0.9],
            },
        )
        assert response.status_code == 200

        data = response.json()
        # With low spending, all allocations should have high success rates
        for result in data["results"]:
            assert result["success_rate"] >= 0.7

    def test_aggressive_spending_scenario(
        self, base_params, stub_allocation_batch
    ):
        """Test scenario with aggressive spending rate."""
        aggressive_params = base_params.model_copy(
            update={
                "annual_spending": 60_000,  # 12% withdrawal rate
            }
        )

        response = client.post(
            "/compare-allocations",
            json={
                "base_input": aggressive_params.model_dump(),
                "allocations": [0.4, 0.8],
            },
        )
        assert response.status_code == 200

        data = response.json()
        # With high spending, some allocations should show lower success
        assert len(data["results"]) == 2

    def test_long_horizon_scenario(self, base_params, stub_allocation_batch):
        """Test scenario with long planning horizon."""
        long_horizon_params = base_params.model_copy(
            update={
                "current_age": 50,
                "max_age": 100,  # 50 year horizon
            }
        )

        response = client.post(
            "/compare-allocations",
            json={
                "base_input": long_horizon_params.model_dump(),
                "allocations": [0.5, 1.0],
            },
        )
        assert response.status_code == 200


class TestAllocationSummary:
    """Test allocation summary logic."""

    def test_summary_provided(self, base_params, stub_allocation_batch):
        """Test that a neutral summary is provided."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert len(data["summary"]) > 0

    def test_summary_references_allocations(
        self, base_params, stub_allocation_batch
    ):
        """Test that summary mentions allocation percentages."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
                "allocations": [0.4, 0.6, 0.8],
            },
        )
        assert response.status_code == 200

        data = response.json()
        summary = data["summary"]
        assert "%" in summary or "allocation" in summary.lower() or "stocks" in summary.lower()
