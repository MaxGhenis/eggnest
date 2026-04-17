"""Deterministic golden cases for simulator regression tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eggnest.models import AnnuityInput, Holding, SimulationInput, SpouseInput
from eggnest.simulation import MonteCarloSimulator

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "simulation_golden_results.json"
)


@dataclass(frozen=True)
class GoldenSimulationCase:
    """Named deterministic simulation case."""

    name: str
    params: SimulationInput


def get_simulation_golden_cases() -> tuple[GoldenSimulationCase, ...]:
    """Return the canonical deterministic simulator regression cases."""
    return (
        GoldenSimulationCase(
            name="legacy_real_spending_bridge_income",
            params=SimulationInput(
                initial_capital=850_000,
                annual_spending=58_000,
                social_security_monthly=1_900,
                social_security_start_age=67,
                pension_annual=8_000,
                employment_income=25_000,
                employment_growth_rate=0.02,
                retirement_age=66,
                current_age=64,
                max_age=69,
                gender="male",
                state="CA",
                filing_status="single",
                spending_mode="real",
                inflation_model="constant",
                inflation_rate=0.025,
                stock_allocation=0.6,
                return_model="bootstrap",
                stock_index="sp500",
                bond_index="treasury",
                include_mortality=False,
                n_simulations=100,
                random_seed=20260330,
            ),
        ),
        GoldenSimulationCase(
            name="holdings_taxable_first_joint_household",
            params=SimulationInput(
                holdings=[
                    Holding(
                        account_type="traditional_401k",
                        fund="sp500",
                        balance=350_000,
                    ),
                    Holding(account_type="roth_ira", fund="sp500", balance=125_000),
                    Holding(
                        account_type="taxable",
                        fund="treasury",
                        balance=180_000,
                        cost_basis=145_000,
                    ),
                    Holding(
                        account_type="taxable",
                        fund="sp500",
                        balance=90_000,
                        cost_basis=70_000,
                    ),
                ],
                withdrawal_strategy="taxable_first",
                annual_spending=72_000,
                social_security_monthly=2_200,
                social_security_start_age=67,
                pension_annual=6_000,
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
                inflation_model="constant",
                inflation_rate=0.025,
                social_security_inflation_adjusted=True,
                include_mortality=False,
                n_simulations=100,
                random_seed=20260331,
            ),
        ),
        GoldenSimulationCase(
            name="holdings_prorata_rmd_annuity",
            params=SimulationInput(
                holdings=[
                    Holding(
                        account_type="traditional_401k",
                        fund="treasury",
                        balance=420_000,
                    ),
                    Holding(
                        account_type="traditional_ira",
                        fund="sp500",
                        balance=220_000,
                    ),
                    Holding(account_type="roth_ira", fund="sp500", balance=80_000),
                    Holding(
                        account_type="taxable",
                        fund="treasury",
                        balance=60_000,
                        cost_basis=55_000,
                    ),
                ],
                withdrawal_strategy="pro_rata",
                annual_spending=68_000,
                social_security_monthly=2_100,
                social_security_start_age=70,
                current_age=73,
                max_age=78,
                gender="female",
                state="NY",
                filing_status="single",
                has_annuity=True,
                annuity=AnnuityInput(
                    monthly_payment=800,
                    annuity_type="life_with_guarantee",
                    guarantee_years=10,
                ),
                annuity_cola_rate=0.02,
                spending_mode="nominal",
                inflation_model="constant",
                inflation_rate=0.02,
                include_mortality=False,
                n_simulations=100,
                random_seed=20260401,
            ),
        ),
    )


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _round_rate(value: float) -> float:
    return round(float(value), 6)


def _normalize_year_breakdown(result) -> list[dict[str, Any]]:
    years = []
    for year in result.year_breakdown:
        years.append(
            {
                "age": year.age,
                "year_index": year.year_index,
                "portfolio_start": _round_money(year.portfolio_start),
                "portfolio_end": _round_money(year.portfolio_end),
                "portfolio_return": _round_rate(year.portfolio_return),
                "inflation_rate": _round_rate(year.inflation_rate),
                "cumulative_inflation": _round_rate(year.cumulative_inflation),
                "spending_target": _round_money(year.spending_target),
                "spending_target_real": _round_money(year.spending_target_real),
                "employment_income": _round_money(year.employment_income),
                "social_security": _round_money(year.social_security),
                "pension": _round_money(year.pension),
                "dividends": _round_money(year.dividends),
                "annuity": _round_money(year.annuity),
                "total_income": _round_money(year.total_income),
                "withdrawal": _round_money(year.withdrawal),
                "federal_tax": _round_money(year.federal_tax),
                "state_tax": _round_money(year.state_tax),
                "total_tax": _round_money(year.total_tax),
                "effective_tax_rate": _round_rate(year.effective_tax_rate),
                "net_income": _round_money(year.net_income),
            }
        )
    return years


def normalize_simulation_result(result) -> dict[str, Any]:
    """Normalize a simulation result into a stable golden snapshot shape."""
    return {
        "success_rate": _round_rate(result.success_rate),
        "median_final_value": _round_money(result.median_final_value),
        "mean_final_value": _round_money(result.mean_final_value),
        "median_final_value_real": _round_money(result.median_final_value_real),
        "mean_final_value_real": _round_money(result.mean_final_value_real),
        "percentiles": {
            key: _round_money(value) for key, value in result.percentiles.items()
        },
        "percentiles_real": {
            key: _round_money(value) for key, value in result.percentiles_real.items()
        },
        "median_depletion_age": result.median_depletion_age,
        "median_depletion_year": (
            None
            if result.median_depletion_year is None
            else _round_rate(result.median_depletion_year)
        ),
        "total_withdrawn_median": _round_money(result.total_withdrawn_median),
        "total_taxes_median": _round_money(result.total_taxes_median),
        "initial_withdrawal_rate": _round_rate(result.initial_withdrawal_rate),
        "prob_10_year_failure": _round_rate(result.prob_10_year_failure),
        "percentile_path_p50": [
            _round_money(value) for value in result.percentile_paths["p50"]
        ],
        "year_breakdown": _normalize_year_breakdown(result),
    }


def generate_simulation_goldens() -> dict[str, dict[str, Any]]:
    """Run all deterministic simulator cases and return normalized snapshots."""
    return {
        case.name: normalize_simulation_result(MonteCarloSimulator(case.params).run())
        for case in get_simulation_golden_cases()
    }


def load_simulation_golden_fixture() -> dict[str, dict[str, Any]]:
    """Load the checked-in simulator golden fixture."""
    return json.loads(FIXTURE_PATH.read_text())


def write_simulation_golden_fixture() -> None:
    """Regenerate the checked-in simulator golden fixture."""
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(generate_simulation_goldens(), indent=2, sort_keys=True) + "\n"
    )
