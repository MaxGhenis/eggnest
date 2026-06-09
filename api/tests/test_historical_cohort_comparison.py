"""Tests for historical cohort comparison helpers and surfaces."""

from types import SimpleNamespace

import numpy as np
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from eggnest.cli import main as cli_main
from eggnest.comparisons import compare_historical_cohorts
from eggnest.models import (
    HistoricalCohortComparisonInput,
    Holding,
    SimulationInput,
)
from eggnest.returns import (
    generate_blended_historical_cohort_returns,
    get_blended_historical_series,
)
from eggnest.simulation import MonteCarloSimulator
from main import app

client = TestClient(app)


class FakeHistoricalSimulator:
    """Fast deterministic simulator for historical comparison contract tests."""

    seen: list[tuple[int, str, str, tuple[int, int]]] = []

    def __init__(self, params, return_paths=None):
        self.params = params
        self.return_paths = return_paths
        self.seen.append(
            (
                params.n_simulations,
                params.stock_index,
                params.bond_index,
                return_paths[0].shape,
            )
        )

    def run(self):
        n_paths = self.params.n_simulations
        n_years = self.params.max_age - self.params.current_age
        self._failure_year = np.full(n_paths, n_years + 1, dtype=float)
        self._failure_year[0] = 1
        self._success_mask = self._failure_year > n_years
        self._final_values = np.arange(n_paths, dtype=float) * 100_000
        self._total_taxes = np.arange(n_paths, dtype=float) * 1_000
        self._total_withdrawn = np.full(n_paths, 50_000.0)
        return SimpleNamespace(success_rate=float(np.mean(self._success_mask)))


def simple_input() -> SimulationInput:
    """Small simple-portfolio scenario for cohort tests."""
    return SimulationInput(
        initial_capital=500_000,
        annual_spending=40_000,
        current_age=65,
        max_age=67,
        state="CA",
        n_simulations=100,
        include_mortality=False,
        stock_allocation=0.6,
    )


def zero_taxes(self, capital_gains_array, *args, **kwargs):
    """Tax stub for deterministic simulator path tests."""
    n_scenarios = len(capital_gains_array)
    zeros = np.zeros(n_scenarios)
    return {
        "federal_income_tax": zeros,
        "state_income_tax": zeros,
        "taxable_income": zeros,
        "total_tax": zeros,
        "effective_tax_rate": zeros,
    }


def test_generate_blended_historical_cohort_returns_uses_contiguous_years():
    years, price, dividends = get_blended_historical_series(
        stock_allocation=0.6,
        stock_index="sp500",
        bond_index="treasury",
    )

    start_years, price_paths, dividend_paths = (
        generate_blended_historical_cohort_returns(
            n_years=3,
            stock_allocation=0.6,
            stock_index="sp500",
            bond_index="treasury",
            start_years=[1928, 1929],
        )
    )

    start_idx = int(np.where(years == 1928)[0][0])
    assert start_years.tolist() == [1928, 1929]
    assert price_paths.shape == (2, 3)
    assert dividend_paths.shape == (2, 3)
    assert price_paths[0].tolist() == pytest.approx(price[start_idx : start_idx + 3])
    assert dividend_paths[0].tolist() == pytest.approx(
        dividends[start_idx : start_idx + 3]
    )


def test_generate_blended_historical_cohort_returns_rejects_invalid_start_year():
    with pytest.raises(ValueError, match="Invalid historical start year"):
        generate_blended_historical_cohort_returns(
            n_years=10,
            stock_index="sp500",
            bond_index="treasury",
            start_years=[2020],
        )


def test_simulator_uses_explicit_return_paths(monkeypatch):
    monkeypatch.setattr(
        "eggnest.simulation.TaxCalculator.calculate_batch_taxes", zero_taxes
    )
    params = SimulationInput(
        initial_capital=1_000,
        annual_spending=1,
        current_age=65,
        max_age=67,
        state="CA",
        n_simulations=100,
        include_mortality=False,
        inflation_rate=0.0,  # pin flat spending for the exact-arithmetic check
    )
    price_paths = np.full((100, 2), 0.10)
    dividend_paths = np.zeros((100, 2))

    simulator = MonteCarloSimulator(
        params,
        return_paths=(price_paths, dividend_paths),
    )
    result = simulator.run()

    assert result.median_final_value == pytest.approx(1207.9)
    assert simulator._paths[0].tolist() == pytest.approx([1000, 1099, 1207.9])


def test_historical_cohort_comparison_requires_simple_portfolio():
    base = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=500_000)],
        annual_spending=40_000,
        current_age=65,
        max_age=67,
        state="CA",
        n_simulations=100,
    )

    with pytest.raises(ValueError, match="simple stock/bond portfolio mode"):
        HistoricalCohortComparisonInput(base_input=base)


def test_compare_historical_cohorts_maps_paths_to_start_years(monkeypatch):
    monkeypatch.setattr(
        "eggnest.comparisons.MonteCarloSimulator", FakeHistoricalSimulator
    )
    FakeHistoricalSimulator.seen = []

    result = compare_historical_cohorts(
        HistoricalCohortComparisonInput(
            base_input=simple_input(),
            start_years=[1928, 1929],
        )
    )

    assert result.n_years == 2
    assert result.cohort_success_rate == 0.5
    assert result.worst_start_year == 1928
    assert result.best_start_year == 1929
    assert result.results[0].end_year == 1929
    assert result.results[0].depletion_age == 66
    assert FakeHistoricalSimulator.seen == [(2, "sp500", "treasury", (2, 2))]


def test_compare_historical_cohorts_endpoint(monkeypatch):
    monkeypatch.setattr(
        "eggnest.comparisons.MonteCarloSimulator", FakeHistoricalSimulator
    )

    response = client.post(
        "/compare-historical-cohorts",
        json={
            "base_input": simple_input().model_dump(),
            "start_years": [1928, 1929],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cohort_success_rate"] == 0.5
    assert data["worst_start_year"] == 1928
    assert len(data["results"]) == 2


def test_compare_historical_cohorts_cli_outputs_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "eggnest.comparisons.MonteCarloSimulator", FakeHistoricalSimulator
    )
    scenario_file = tmp_path / "scenario.yaml"
    scenario_file.write_text(
        """
initial_capital: 500000
annual_spending: 40000
current_age: 65
max_age: 67
state: CA
n_simulations: 100
stock_allocation: 0.6
"""
    )

    result = CliRunner().invoke(
        cli_main,
        [
            "compare",
            "historical-cohorts",
            str(scenario_file),
            "--start-year",
            "1928",
            "--start-year",
            "1929",
        ],
    )

    assert result.exit_code == 0
    assert '"cohort_success_rate": 0.5' in result.output
    assert '"worst_start_year": 1928' in result.output
