"""Tests for withdrawal strategy comparison helpers and surfaces."""

from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from eggnest.cli import main as cli_main
from eggnest.comparisons import compare_withdrawal_strategies
from eggnest.models import (
    Holding,
    SimulationInput,
    WithdrawalStrategyComparisonInput,
)
from main import app

client = TestClient(app)

STRATEGY_FIXTURES = {
    "taxable_first": (0.80, 500_000, 110_000),
    "traditional_first": (0.85, 540_000, 95_000),
    "roth_first": (0.82, 515_000, 105_000),
    "pro_rata": (0.84, 530_000, 100_000),
}


class FakeSimulator:
    """Fast deterministic simulator keyed by withdrawal strategy."""

    seen: list[tuple[str, int | None]] = []

    def __init__(self, params):
        self.params = params
        self.seen.append((params.withdrawal_strategy, params.random_seed))

    def run(self):
        success_rate, final_value, taxes = STRATEGY_FIXTURES[
            self.params.withdrawal_strategy
        ]
        return SimpleNamespace(
            success_rate=success_rate,
            median_final_value=final_value,
            total_taxes_median=taxes,
            total_withdrawn_median=700_000,
            median_depletion_age=None,
            initial_withdrawal_rate=4.0,
        )


@pytest.fixture
def holdings_input() -> SimulationInput:
    """US holdings-mode scenario used by comparison tests."""
    return SimulationInput(
        holdings=[
            Holding(account_type="traditional_401k", fund="vt", balance=300_000),
            Holding(account_type="roth_ira", fund="vt", balance=100_000),
            Holding(account_type="taxable", fund="bnd", balance=100_000),
        ],
        annual_spending=40_000,
        current_age=65,
        max_age=90,
        state="CA",
        n_simulations=100,
        withdrawal_strategy="taxable_first",
    )


def test_withdrawal_strategy_comparison_requires_holdings():
    base = SimulationInput(
        initial_capital=500_000,
        annual_spending=40_000,
        current_age=65,
        max_age=90,
        state="CA",
    )

    with pytest.raises(ValueError, match="holdings are required"):
        WithdrawalStrategyComparisonInput(base_input=base)


def test_compare_withdrawal_strategies_uses_shared_seed(holdings_input, monkeypatch):
    monkeypatch.setattr("eggnest.comparisons.MonteCarloSimulator", FakeSimulator)
    FakeSimulator.seen = []

    result = compare_withdrawal_strategies(
        WithdrawalStrategyComparisonInput(base_input=holdings_input, random_seed=123)
    )

    assert result.base_strategy == "taxable_first"
    assert result.shared_random_seed == 123
    assert {row.withdrawal_strategy for row in result.results} == set(STRATEGY_FIXTURES)
    assert all(seed == 123 for _, seed in FakeSimulator.seen)

    traditional = next(
        row for row in result.results if row.withdrawal_strategy == "traditional_first"
    )
    assert traditional.success_rate_delta_vs_base == pytest.approx(0.05)
    assert traditional.total_taxes_delta_vs_base == -15_000


def test_compare_withdrawal_strategies_endpoint(holdings_input, monkeypatch):
    monkeypatch.setattr("eggnest.comparisons.MonteCarloSimulator", FakeSimulator)
    FakeSimulator.seen = []

    response = client.post(
        "/compare-withdrawal-strategies",
        json={"base_input": holdings_input.model_dump(), "random_seed": 456},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["base_strategy"] == "taxable_first"
    assert data["shared_random_seed"] == 456
    assert len(data["results"]) == 4


def test_compare_withdrawal_strategies_cli_outputs_json(
    tmp_path, holdings_input, monkeypatch
):
    monkeypatch.setattr("eggnest.comparisons.MonteCarloSimulator", FakeSimulator)
    FakeSimulator.seen = []
    scenario_file = tmp_path / "scenario.yaml"
    scenario_file.write_text(
        """
holdings:
  - account_type: traditional_401k
    fund: vt
    balance: 300000
  - account_type: roth_ira
    fund: vt
    balance: 100000
  - account_type: taxable
    fund: bnd
    balance: 100000
annual_spending: 40000
current_age: 65
max_age: 90
state: CA
n_simulations: 100
withdrawal_strategy: taxable_first
"""
    )

    result = CliRunner().invoke(
        cli_main,
        [
            "compare",
            "withdrawal-strategies",
            str(scenario_file),
            "--strategy",
            "taxable_first",
            "--strategy",
            "traditional_first",
            "--random-seed",
            "789",
        ],
    )

    assert result.exit_code == 0
    assert '"base_strategy": "taxable_first"' in result.output
    assert '"shared_random_seed": 789' in result.output
