"""Deterministic historical cohort backtesting."""

from __future__ import annotations

import numpy as np

from .models import (
    HistoricalBacktestInput,
    HistoricalBacktestResult,
    HistoricalCohortResult,
    SimulationInput,
)
from .returns import (
    generate_historical_blended_return_paths,
    generate_historical_fund_return_paths,
    generate_inflation_paths,
)
from .simulation import MonteCarloSimulator, SimulationPathOverrides


def _build_historical_overrides(
    params: SimulationInput,
    start_years: list[int] | None,
) -> tuple[SimulationPathOverrides, list[int]]:
    """Build exact historical market and inflation paths for a backtest run."""
    n_years = params.max_age - params.current_age

    if params.holdings:
        funds = tuple(dict.fromkeys(holding.fund for holding in params.holdings))
        fund_returns, sampled_years, valid_start_years = (
            generate_historical_fund_return_paths(
                funds=funds,
                n_years=n_years,
                start_years=start_years,
            )
        )
        inflation_rates = generate_inflation_paths(
            n_simulations=sampled_years.shape[0],
            n_years=n_years,
            model=params.inflation_model,
            inflation_rate=params.inflation_rate,
            method="historical",
            sampled_years=sampled_years,
        )
        return (
            SimulationPathOverrides(
                sampled_years=sampled_years,
                inflation_rates=inflation_rates,
                fund_returns=fund_returns,
            ),
            [int(year) for year in (start_years or valid_start_years.tolist())],
        )

    price_growth, div_yields, sampled_years, valid_start_years = (
        generate_historical_blended_return_paths(
            n_years=n_years,
            stock_allocation=params.stock_allocation,
            stock_index=params.stock_index,
            bond_index=params.bond_index,
            start_years=start_years,
        )
    )
    inflation_rates = generate_inflation_paths(
        n_simulations=sampled_years.shape[0],
        n_years=n_years,
        model=params.inflation_model,
        inflation_rate=params.inflation_rate,
        method="historical",
        sampled_years=sampled_years,
    )
    return (
        SimulationPathOverrides(
            price_growth=price_growth,
            div_yields=div_yields,
            sampled_years=sampled_years,
            inflation_rates=inflation_rates,
        ),
        [int(year) for year in (start_years or valid_start_years.tolist())],
    )


def run_historical_backtest(
    request: HistoricalBacktestInput | SimulationInput,
) -> HistoricalBacktestResult:
    """
    Replay the current EggNest engine over exact historical return cohorts.

    This runner disables mortality so each cohort is deterministic and comparable.
    """
    if isinstance(request, SimulationInput):
        backtest_input = HistoricalBacktestInput(base_input=request)
    else:
        backtest_input = request

    params = backtest_input.base_input
    n_years = params.max_age - params.current_age
    overrides, resolved_start_years = _build_historical_overrides(
        params, backtest_input.start_years
    )

    cohort_params = params.model_copy(
        update={
            "n_simulations": len(resolved_start_years),
            "include_mortality": False,
            "random_seed": 0,
        }
    )
    simulator = MonteCarloSimulator(cohort_params, path_overrides=overrides)
    summary = simulator.run()

    paths = simulator._paths
    real_paths = simulator._real_paths
    failure_year = simulator._failure_year
    total_withdrawn = simulator._total_withdrawn
    total_taxes = simulator._total_taxes
    total_medicare_premiums = simulator._total_medicare_premiums
    total_roth_conversions = simulator._total_roth_conversions

    cohort_results = []
    for index, start_year in enumerate(resolved_start_years):
        cohort_failure_year = float(failure_year[index])
        failure_age = None
        success = cohort_failure_year > n_years
        if not success:
            failure_age = int(params.current_age + cohort_failure_year)
        cohort_results.append(
            HistoricalCohortResult(
                start_year=start_year,
                success=success,
                final_value=float(paths[index, -1]),
                final_value_real=float(real_paths[index, -1]),
                total_withdrawn=float(total_withdrawn[index]),
                total_taxes=float(total_taxes[index]),
                total_medicare_premiums=float(total_medicare_premiums[index]),
                total_roth_conversions=float(total_roth_conversions[index]),
                failure_age=failure_age,
            )
        )

    strongest = max(cohort_results, key=lambda cohort: cohort.final_value_real)
    weakest = min(cohort_results, key=lambda cohort: cohort.final_value_real)

    return HistoricalBacktestResult(
        horizon_years=n_years,
        start_years=resolved_start_years,
        results=cohort_results,
        success_rate=summary.success_rate,
        median_final_value=summary.median_final_value,
        median_final_value_real=summary.median_final_value_real,
        total_withdrawn_median=summary.total_withdrawn_median,
        total_taxes_median=summary.total_taxes_median,
        total_medicare_premiums_median=summary.total_medicare_premiums_median,
        total_roth_conversions_median=summary.total_roth_conversions_median,
        strongest_start_year=strongest.start_year,
        weakest_start_year=weakest.start_year,
        median_path=[float(np.median(paths[:, i])) for i in range(n_years + 1)],
        median_path_real=[
            float(np.median(real_paths[:, i])) for i in range(n_years + 1)
        ],
    )
