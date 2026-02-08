"""Tests for asset allocation comparison API endpoint."""

import pytest
from fastapi.testclient import TestClient

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
        max_age=90,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,  # Small for faster tests
    )


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
            optimal_for_success=1.0,
            optimal_for_safety=0.4,
            recommendation="",
        )
        assert result.optimal_for_success == 1.0


class TestAllocationEndpoint:
    """Test /compare-allocations API endpoint."""

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

    def test_compare_allocations_default_allocations(self, base_params):
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

    def test_compare_allocations_result_fields(self, base_params):
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

    def test_compare_allocations_identifies_optimal(self, base_params):
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

        # Should have optimal allocations identified
        assert "optimal_for_success" in data
        assert 0 <= data["optimal_for_success"] <= 1

        assert "optimal_for_safety" in data
        assert 0 <= data["optimal_for_safety"] <= 1

    def test_compare_allocations_volatility_ordering(self, base_params):
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

    def test_conservative_investor_scenario(self, base_params):
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

    def test_aggressive_spending_scenario(self, base_params):
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

    def test_long_horizon_scenario(self, base_params):
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


class TestAllocationRecommendation:
    """Test allocation recommendation logic."""

    def test_recommendation_provided(self, base_params):
        """Test that a recommendation is provided."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "recommendation" in data
        assert len(data["recommendation"]) > 0

    def test_recommendation_references_allocations(self, base_params):
        """Test that recommendation mentions allocation percentages."""
        response = client.post(
            "/compare-allocations",
            json={
                "base_input": base_params.model_dump(),
                "allocations": [0.4, 0.6, 0.8],
            },
        )
        assert response.status_code == 200

        data = response.json()
        recommendation = data["recommendation"]
        # Recommendation should mention percentage or allocation
        assert "%" in recommendation or "allocation" in recommendation.lower()
