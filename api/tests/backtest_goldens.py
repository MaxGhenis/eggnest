"""Deterministic golden cases for historical backtest regression tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eggnest.backtest import run_historical_backtest
from eggnest.models import (
    HistoricalBacktestInput,
    Holding,
    SimulationInput,
    SpouseInput,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "historical_backtest_golden_results.json"
)


@dataclass(frozen=True)
class GoldenBacktestCase:
    """Named deterministic historical backtest case."""

    name: str
    request: HistoricalBacktestInput


def get_backtest_golden_cases() -> tuple[GoldenBacktestCase, ...]:
    """Return canonical deterministic historical backtest cases."""
    return (
        GoldenBacktestCase(
            name="legacy_selected_cohorts",
            request=HistoricalBacktestInput(
                base_input=SimulationInput(
                    initial_capital=1_000_000,
                    annual_spending=45_000,
                    social_security_monthly=1_800,
                    social_security_start_age=67,
                    current_age=65,
                    max_age=70,
                    gender="male",
                    state="CA",
                    filing_status="single",
                    stock_allocation=0.6,
                    spending_mode="real",
                    inflation_model="historical",
                    include_mortality=True,
                    n_simulations=100,
                ),
                start_years=[1966, 1973, 2000, 2008],
            ),
        ),
        GoldenBacktestCase(
            name="holdings_selected_cohorts",
            request=HistoricalBacktestInput(
                base_input=SimulationInput(
                    holdings=[
                        Holding(
                            account_type="traditional_401k",
                            fund="sp500",
                            balance=320_000,
                        ),
                        Holding(account_type="roth_ira", fund="sp500", balance=80_000),
                        Holding(
                            account_type="taxable",
                            fund="treasury",
                            balance=150_000,
                            cost_basis=120_000,
                        ),
                        Holding(
                            account_type="taxable",
                            fund="sp500",
                            balance=100_000,
                            cost_basis=75_000,
                        ),
                    ],
                    withdrawal_strategy="taxable_first",
                    annual_spending=70_000,
                    social_security_monthly=2_200,
                    social_security_start_age=67,
                    current_age=66,
                    max_age=71,
                    gender="male",
                    state="CA",
                    filing_status="married_filing_jointly",
                    has_spouse=True,
                    spouse=SpouseInput(
                        age=64,
                        gender="female",
                        social_security_monthly=1_500,
                        social_security_start_age=67,
                        pension_annual=4_000,
                        employment_income=18_000,
                        employment_growth_rate=0.03,
                        retirement_age=65,
                    ),
                    spending_mode="real",
                    inflation_model="historical",
                    include_mortality=True,
                    n_simulations=100,
                ),
                start_years=[1966, 1981, 2000, 2008],
            ),
        ),
    )


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _round_rate(value: float) -> float:
    return round(float(value), 6)


def normalize_backtest_result(result) -> dict[str, Any]:
    """Normalize a historical backtest result into a stable snapshot shape."""
    return {
        "horizon_years": result.horizon_years,
        "start_years": result.start_years,
        "success_rate": _round_rate(result.success_rate),
        "median_final_value": _round_money(result.median_final_value),
        "median_final_value_real": _round_money(result.median_final_value_real),
        "total_withdrawn_median": _round_money(result.total_withdrawn_median),
        "total_taxes_median": _round_money(result.total_taxes_median),
        "strongest_start_year": result.strongest_start_year,
        "weakest_start_year": result.weakest_start_year,
        "median_path": [_round_money(value) for value in result.median_path],
        "median_path_real": [_round_money(value) for value in result.median_path_real],
        "results": [
            {
                "start_year": cohort.start_year,
                "success": cohort.success,
                "final_value": _round_money(cohort.final_value),
                "final_value_real": _round_money(cohort.final_value_real),
                "total_withdrawn": _round_money(cohort.total_withdrawn),
                "total_taxes": _round_money(cohort.total_taxes),
                "failure_age": cohort.failure_age,
            }
            for cohort in result.results
        ],
    }


def generate_backtest_goldens() -> dict[str, dict[str, Any]]:
    """Run all deterministic historical backtests and return normalized snapshots."""
    return {
        case.name: normalize_backtest_result(run_historical_backtest(case.request))
        for case in get_backtest_golden_cases()
    }


def load_backtest_golden_fixture() -> dict[str, dict[str, Any]]:
    """Load the checked-in historical backtest fixture."""
    return json.loads(FIXTURE_PATH.read_text())


def write_backtest_golden_fixture() -> None:
    """Regenerate the checked-in historical backtest fixture."""
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(generate_backtest_goldens(), indent=2, sort_keys=True) + "\n"
    )
