"""Smoke tests for the UK Monte Carlo simulator."""

from __future__ import annotations

import numpy as np
import pytest

from eggnest.models_uk import UKSimulationInput, UKSimulationResult
from eggnest.simulation_uk import run_uk_simulation, run_uk_simulation_with_progress
from eggnest.tax_uk import LATEST_PARAMETER_YEAR, UKYearInputs, calculate_uk_tax


@pytest.fixture
def basic_input() -> UKSimulationInput:
    return UKSimulationInput(
        current_age=65,
        max_age=70,
        annual_spending=25000,
        isa_balance=100000,
        sipp_balance=100000,
        gia_balance=0,
        state_pension_annual=11502,
        state_pension_start_age=67,
        n_simulations=200,
        random_seed=7,
    )


def test_uk_tax_batch_runs_quickly():
    n = 100
    inputs = UKYearInputs(
        age=70,
        year=2025,
        state_pension=np.full(n, 11502.0),
        private_pension_income=np.full(n, 20000.0),
        savings_interest=np.zeros(n),
        dividend_income=np.zeros(n),
        employment_income=np.zeros(n),
    )
    result = calculate_uk_tax(inputs)
    assert result.net_income.shape == (n,)
    assert result.total_tax.shape == (n,)
    assert np.all(result.net_income > 0)
    # All paths identical → all outputs identical
    assert np.allclose(result.net_income, result.net_income[0])


def test_future_year_falls_back_to_latest_parameters():
    n = 2
    inputs = UKYearInputs(
        age=75,
        year=2060,
        state_pension=np.full(n, 11502.0),
        private_pension_income=np.full(n, 20000.0),
        savings_interest=np.zeros(n),
        dividend_income=np.zeros(n),
        employment_income=np.zeros(n),
    )
    # Should not raise — clipped to LATEST_PARAMETER_YEAR
    result = calculate_uk_tax(inputs)
    assert result.net_income.shape == (n,)
    assert LATEST_PARAMETER_YEAR >= 2029


def test_run_uk_simulation_returns_structured_result(basic_input):
    result = run_uk_simulation(basic_input)
    assert isinstance(result, UKSimulationResult)
    assert 0.0 <= result.success_rate <= 1.0
    assert len(result.year_breakdown) == basic_input.max_age - basic_input.current_age + 1
    for key in ("p5", "p25", "p50", "p75", "p95"):
        assert key in result.percentile_paths
        assert len(result.percentile_paths[key]) == len(result.year_breakdown)


def test_streaming_variant_emits_progress_then_result(basic_input):
    events = list(run_uk_simulation_with_progress(basic_input))
    n_years = basic_input.max_age - basic_input.current_age + 1
    progress_events = [e for e in events if e["type"] == "progress"]
    final_events = [e for e in events if e["type"] == "result"]
    assert len(progress_events) == n_years
    assert progress_events[-1]["current_year"] == n_years
    assert len(final_events) == 1
    assert "success_rate" in final_events[0]["result"]


def test_pre_mpa_paths_cannot_touch_sipp():
    """SIPP drawdown is locked until Minimum Pension Age (55)."""
    inp = UKSimulationInput(
        current_age=50,
        max_age=54,  # every year in this run is pre-MPA
        annual_spending=40000,
        isa_balance=0,
        sipp_balance=500000,
        gia_balance=0,
        state_pension_annual=0,
        state_pension_start_age=67,
        n_simulations=100,
        random_seed=1,
        include_mortality=False,
    )
    result = run_uk_simulation(inp)
    # Every year breakdown should show zero SIPP drawdown pre-MPA, even though
    # the spending target is far above the accessible ISA/GIA (both zero).
    for b in result.year_breakdown:
        assert b.sipp_withdrawal == 0.0, f"SIPP withdrawn at age {b.age} (pre-MPA)"


def test_tfc_lowers_taxes_vs_full_taxable_sipp(basic_input):
    """The 25 % tax-free split should not produce higher tax than full-taxable SIPP."""
    # Indirect check: when the simulation leans heavily on SIPP (low ISA/GIA),
    # total tax paid should be materially below a naive 20 %-of-SIPP upper bound.
    heavy_sipp = basic_input.model_copy(
        update={
            "isa_balance": 0,
            "gia_balance": 0,
            "sipp_balance": 400_000,
            "annual_spending": 20_000,
            "state_pension_annual": 0,
            "state_pension_start_age": 70,
            "max_age": 72,
        }
    )
    result = run_uk_simulation(heavy_sipp)
    # Year 0 median breakdown
    b0 = result.year_breakdown[0]
    assert b0.sipp_withdrawal > 0, "should be drawing SIPP with no other income"
    # 25 % tax-free portion → effective tax rate should be well below 20 %.
    assert b0.effective_tax_rate < 0.20
