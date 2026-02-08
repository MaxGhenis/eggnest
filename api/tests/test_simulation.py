"""Tests for the Monte Carlo simulation engine."""

from eggnest.models import SimulationInput
from eggnest.simulation import MonteCarloSimulator


def test_simulation_basic():
    """Test basic simulation runs without errors."""
    params = SimulationInput(
        initial_capital=1_000_000,
        annual_spending=48000,
        social_security_monthly=2000,
        current_age=65,
        max_age=75,  # 10 years
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,  # Small for testing
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    assert 0 <= result.success_rate <= 1
    assert result.median_final_value >= 0
    assert result.mean_final_value >= 0
    assert len(result.percentiles) == 5
    assert len(result.percentile_paths["p50"]) == 11  # n_years + 1


def test_simulation_high_withdrawal_depletes():
    """Test that very high withdrawals lead to depletion."""
    params = SimulationInput(
        initial_capital=100_000,
        annual_spending=120_000,  # Very high relative to capital
        social_security_monthly=0,
        current_age=65,
        max_age=95,  # 30 years
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
        include_mortality=False,  # Disable mortality for pure depletion test
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    # Should have high depletion rate
    assert result.success_rate < 0.5


def test_simulation_low_withdrawal_succeeds():
    """Test that conservative withdrawals have high success rate."""
    params = SimulationInput(
        initial_capital=2_000_000,
        annual_spending=36000,  # ~1.8% withdrawal rate
        social_security_monthly=2000,
        current_age=65,
        max_age=95,  # 30 years
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    # Should have high success rate
    assert result.success_rate > 0.8


def test_simulation_percentiles_ordered():
    """Test that percentiles are in correct order."""
    params = SimulationInput(
        initial_capital=1_000_000,
        annual_spending=48000,
        current_age=65,
        max_age=75,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    assert result.percentiles["p5"] <= result.percentiles["p25"]
    assert result.percentiles["p25"] <= result.percentiles["p50"]
    assert result.percentiles["p50"] <= result.percentiles["p75"]
    assert result.percentiles["p75"] <= result.percentiles["p95"]
