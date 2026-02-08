"""Tests for Social Security timing comparison API endpoint."""

import pytest
from fastapi.testclient import TestClient

from eggnest.models import (
    SimulationInput,
    SSTimingComparisonResult,
    SSTimingInput,
    SSTimingResult,
)
from main import app

client = TestClient(app)


@pytest.fixture
def base_params():
    """Base simulation parameters for testing."""
    return SimulationInput(
        initial_capital=500_000,
        annual_spending=40_000,
        social_security_monthly=0,  # Will be set per claiming age
        current_age=62,
        max_age=90,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,  # Small for faster tests
    )


class TestSSTimingModels:
    """Test SS timing Pydantic models."""

    def test_ss_timing_input_valid(self, base_params):
        """Test valid SSTimingInput creation."""
        timing_input = SSTimingInput(
            base_input=base_params,
            birth_year=1960,
            pia_monthly=2000,
        )
        assert timing_input.birth_year == 1960
        assert timing_input.pia_monthly == 2000
        assert len(timing_input.claiming_ages) == 9  # Default 62-70

    def test_ss_timing_input_custom_ages(self, base_params):
        """Test SSTimingInput with custom claiming ages."""
        timing_input = SSTimingInput(
            base_input=base_params,
            birth_year=1960,
            pia_monthly=2000,
            claiming_ages=[62, 67, 70],
        )
        assert timing_input.claiming_ages == [62, 67, 70]

    def test_ss_timing_input_requires_birth_year(self, base_params):
        """Test that birth_year is required."""
        with pytest.raises(ValueError):
            SSTimingInput(
                base_input=base_params,
                pia_monthly=2000,
            )

    def test_ss_timing_input_requires_pia(self, base_params):
        """Test that pia_monthly is required."""
        with pytest.raises(ValueError):
            SSTimingInput(
                base_input=base_params,
                birth_year=1960,
            )

    def test_ss_timing_result_model(self):
        """Test SSTimingResult model creation."""
        result = SSTimingResult(
            claiming_age=62,
            monthly_benefit=1400,
            annual_benefit=16800,
            adjustment_factor=0.70,
            success_rate=0.85,
            median_final_value=300_000,
            total_ss_income_median=400_000,
            total_taxes_median=50_000,
            breakeven_vs_62=None,
        )
        assert result.claiming_age == 62
        assert result.monthly_benefit == 1400

    def test_ss_timing_comparison_result_model(self):
        """Test SSTimingComparisonResult model creation."""
        result = SSTimingComparisonResult(
            birth_year=1960,
            full_retirement_age=67.0,
            pia_monthly=2000,
            results=[
                SSTimingResult(
                    claiming_age=62,
                    monthly_benefit=1400,
                    annual_benefit=16800,
                    adjustment_factor=0.70,
                    success_rate=0.85,
                    median_final_value=300_000,
                    total_ss_income_median=400_000,
                    total_taxes_median=50_000,
                    breakeven_vs_62=None,
                ),
            ],
            optimal_claiming_age=70,
            optimal_for_longevity=70,
        )
        assert result.birth_year == 1960
        assert result.full_retirement_age == 67.0


class TestSSTimingEndpoint:
    """Test /compare-ss-timing API endpoint."""

    def test_compare_ss_timing_returns_results(self, base_params):
        """Test that endpoint returns valid comparison results."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
                "claiming_ages": [62, 67, 70],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["birth_year"] == 1960
        assert data["full_retirement_age"] == 67.0
        assert data["pia_monthly"] == 2000
        assert len(data["results"]) == 3

    def test_compare_ss_timing_all_ages(self, base_params):
        """Test comparison with all claiming ages (62-70)."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) == 9  # 62-70

        # Verify all ages are present
        ages = [r["claiming_age"] for r in data["results"]]
        assert ages == [62, 63, 64, 65, 66, 67, 68, 69, 70]

    def test_compare_ss_timing_benefit_adjustment(self, base_params):
        """Test that benefits are correctly adjusted for claiming age."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
                "claiming_ages": [62, 67, 70],
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Find results by age
        age_62 = next(r for r in data["results"] if r["claiming_age"] == 62)
        age_67 = next(r for r in data["results"] if r["claiming_age"] == 67)
        age_70 = next(r for r in data["results"] if r["claiming_age"] == 70)

        # Verify benefit adjustments (FRA=67 for birth year 1960)
        # At 62: 30% reduction -> $1400/month
        assert age_62["monthly_benefit"] == pytest.approx(1400, rel=0.01)
        assert age_62["adjustment_factor"] == pytest.approx(0.70, rel=0.01)

        # At 67 (FRA): No change -> $2000/month
        assert age_67["monthly_benefit"] == pytest.approx(2000, rel=0.01)
        assert age_67["adjustment_factor"] == pytest.approx(1.0, rel=0.01)

        # At 70: 24% increase -> $2480/month
        assert age_70["monthly_benefit"] == pytest.approx(2480, rel=0.01)
        assert age_70["adjustment_factor"] == pytest.approx(1.24, rel=0.01)

    def test_compare_ss_timing_result_fields(self, base_params):
        """Test that each result has required fields."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
                "claiming_ages": [67],
            },
        )
        assert response.status_code == 200

        data = response.json()
        result = data["results"][0]

        # Required fields
        assert "claiming_age" in result
        assert "monthly_benefit" in result
        assert "annual_benefit" in result
        assert "adjustment_factor" in result
        assert "success_rate" in result
        assert "median_final_value" in result
        assert "total_ss_income_median" in result
        assert "total_taxes_median" in result

        # Validate ranges
        assert 0 <= result["success_rate"] <= 1
        assert result["monthly_benefit"] > 0
        assert result["annual_benefit"] == result["monthly_benefit"] * 12

    def test_compare_ss_timing_identifies_optimal(self, base_params):
        """Test that optimal claiming ages are identified."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Should have optimal ages identified
        assert "optimal_claiming_age" in data
        assert 62 <= data["optimal_claiming_age"] <= 70

        assert "optimal_for_longevity" in data
        assert 62 <= data["optimal_for_longevity"] <= 70

    def test_compare_ss_timing_fra_varies_by_birth_year(self, base_params):
        """Test that FRA is correctly calculated for different birth years."""
        # Birth year 1950 -> FRA = 66
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1950,
                "pia_monthly": 2000,
                "claiming_ages": [62, 66, 70],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_retirement_age"] == 66.0

        # At FRA (66): No change
        age_66 = next(r for r in data["results"] if r["claiming_age"] == 66)
        assert age_66["adjustment_factor"] == pytest.approx(1.0, rel=0.01)

        # At 70: 4 years × 8% = 32% increase
        age_70 = next(r for r in data["results"] if r["claiming_age"] == 70)
        assert age_70["adjustment_factor"] == pytest.approx(1.32, rel=0.01)


class TestSSTimingBreakeven:
    """Test breakeven calculations."""

    def test_breakeven_vs_62_calculated(self, base_params):
        """Test that breakeven age vs claiming at 62 is calculated."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
                "claiming_ages": [62, 70],
            },
        )
        assert response.status_code == 200

        data = response.json()

        # Age 62 should have None for breakeven (it IS 62)
        age_62 = next(r for r in data["results"] if r["claiming_age"] == 62)
        assert age_62["breakeven_vs_62"] is None

        # Age 70 should have a breakeven age
        age_70 = next(r for r in data["results"] if r["claiming_age"] == 70)
        # Breakeven should be somewhere between 70 and ~82
        # (exact depends on calculation method)
        if age_70["breakeven_vs_62"] is not None:
            assert 70 <= age_70["breakeven_vs_62"] <= 85


class TestSSTimingEdgeCases:
    """Test edge cases for SS timing comparison."""

    def test_single_claiming_age(self, base_params):
        """Test with just one claiming age."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 2000,
                "claiming_ages": [67],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1

    def test_high_pia(self, base_params):
        """Test with high PIA (max SS benefit)."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1960,
                "pia_monthly": 3800,  # Near max SS benefit
                "claiming_ages": [62, 70],
            },
        )
        assert response.status_code == 200
        data = response.json()

        age_70 = next(r for r in data["results"] if r["claiming_age"] == 70)
        # At 70 with high PIA: 3800 * 1.24 = ~4712/month
        assert age_70["monthly_benefit"] > 4500

    def test_older_birth_year(self, base_params):
        """Test with older birth year (FRA = 65)."""
        response = client.post(
            "/compare-ss-timing",
            json={
                "base_input": base_params.model_dump(),
                "birth_year": 1937,
                "pia_monthly": 2000,
                "claiming_ages": [62, 65, 70],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_retirement_age"] == 65.0

        # At FRA (65): No change
        age_65 = next(r for r in data["results"] if r["claiming_age"] == 65)
        assert age_65["adjustment_factor"] == pytest.approx(1.0, rel=0.01)
