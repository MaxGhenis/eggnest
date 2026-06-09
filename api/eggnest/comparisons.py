"""Scenario comparison helpers that reuse the core simulation engines."""

from __future__ import annotations

from .models import (
    HistoricalCohortComparisonInput,
    HistoricalCohortComparisonResult,
    HistoricalCohortResult,
    SimulationResult,
    WithdrawalStrategy,
    WithdrawalStrategyComparisonInput,
    WithdrawalStrategyComparisonResult,
    WithdrawalStrategyResult,
)
from .returns import generate_blended_historical_cohort_returns
from .simulation import MonteCarloSimulator


def compare_withdrawal_strategies(
    comparison: WithdrawalStrategyComparisonInput,
) -> WithdrawalStrategyComparisonResult:
    """Compare withdrawal orders under shared market and tax assumptions.

    This does not implement policy logic. Each row reruns the existing simulator,
    which delegates tax calculations to PolicyEngine.
    """
    base_input = comparison.base_input
    base_strategy = base_input.withdrawal_strategy
    strategies = _unique_strategies([base_strategy, *comparison.strategies])
    shared_seed = (
        comparison.random_seed
        if comparison.random_seed is not None
        else base_input.random_seed
    )

    raw_results: dict[WithdrawalStrategy, SimulationResult] = {}
    for strategy in strategies:
        params = base_input.model_copy(
            update={
                "withdrawal_strategy": strategy,
                "random_seed": shared_seed,
            }
        )
        raw_results[strategy] = MonteCarloSimulator(params).run()

    base_result = raw_results[base_strategy]
    rows = [
        WithdrawalStrategyResult(
            withdrawal_strategy=strategy,
            success_rate=result.success_rate,
            median_final_value=result.median_final_value,
            total_taxes_median=result.total_taxes_median,
            total_withdrawn_median=result.total_withdrawn_median,
            median_depletion_age=result.median_depletion_age,
            initial_withdrawal_rate=result.initial_withdrawal_rate,
            success_rate_delta_vs_base=result.success_rate - base_result.success_rate,
            median_final_value_delta_vs_base=(
                result.median_final_value - base_result.median_final_value
            ),
            total_taxes_delta_vs_base=(
                result.total_taxes_median - base_result.total_taxes_median
            ),
        )
        for strategy, result in raw_results.items()
    ]

    return WithdrawalStrategyComparisonResult(
        base_strategy=base_strategy,
        shared_random_seed=shared_seed,
        results=rows,
        comparison_summary=_summary(rows, base_strategy),
    )


def compare_historical_cohorts(
    comparison: HistoricalCohortComparisonInput,
) -> HistoricalCohortComparisonResult:
    """Compare fixed historical market sequences using the existing simulator.

    This does not implement policy logic. Each historical cohort is a concrete
    market-return path; tax calculations still run through PolicyEngine via the
    simulator's existing tax layer.
    """
    base_input = comparison.base_input
    n_years = base_input.max_age - base_input.current_age
    start_years, price_paths, dividend_paths = (
        generate_blended_historical_cohort_returns(
            n_years=n_years,
            stock_allocation=base_input.stock_allocation,
            stock_index=comparison.stock_index,
            bond_index=comparison.bond_index,
            start_years=comparison.start_years,
        )
    )

    params = base_input.model_copy(
        update={
            "n_simulations": len(start_years),
            "return_model": "historical",
            "stock_index": comparison.stock_index,
            "bond_index": comparison.bond_index,
            "include_mortality": comparison.include_mortality,
        }
    )
    simulator = MonteCarloSimulator(params, return_paths=(price_paths, dividend_paths))
    simulator.run()

    rows = [
        HistoricalCohortResult(
            start_year=int(start_year),
            end_year=int(start_year) + n_years - 1,
            success=bool(simulator._success_mask[path_idx]),
            final_value=float(simulator._final_values[path_idx]),
            total_taxes=float(simulator._total_taxes[path_idx]),
            total_withdrawn=float(simulator._total_withdrawn[path_idx]),
            depletion_age=(
                base_input.current_age + int(simulator._failure_year[path_idx])
                if simulator._failure_year[path_idx] <= n_years
                else None
            ),
        )
        for path_idx, start_year in enumerate(start_years)
    ]

    worst = min(rows, key=lambda row: row.final_value)
    best = max(rows, key=lambda row: row.final_value)
    cohort_success_rate = sum(row.success for row in rows) / len(rows)

    return HistoricalCohortComparisonResult(
        stock_index=comparison.stock_index,
        bond_index=comparison.bond_index,
        stock_allocation=base_input.stock_allocation,
        n_years=n_years,
        cohort_success_rate=cohort_success_rate,
        results=rows,
        worst_start_year=worst.start_year,
        best_start_year=best.start_year,
        worst_final_value=worst.final_value,
        best_final_value=best.final_value,
        comparison_summary=_historical_summary(rows, n_years, cohort_success_rate),
    )


def _unique_strategies(
    strategies: list[WithdrawalStrategy],
) -> list[WithdrawalStrategy]:
    """Deduplicate strategies while preserving caller order."""
    seen: set[WithdrawalStrategy] = set()
    unique = []
    for strategy in strategies:
        if strategy not in seen:
            seen.add(strategy)
            unique.append(strategy)
    return unique


def _historical_summary(
    rows: list[HistoricalCohortResult],
    n_years: int,
    cohort_success_rate: float,
) -> str:
    """Build a factual, non-advice summary of a historical cohort comparison."""
    worst = min(rows, key=lambda row: row.final_value)
    best = max(rows, key=lambda row: row.final_value)
    start_min = min(row.start_year for row in rows)
    start_max = max(row.start_year for row in rows)
    return (
        f"Across {len(rows)} historical cohorts starting {start_min}-{start_max}, "
        f"{cohort_success_rate:.0%} avoided depletion over {n_years} years. "
        f"The lowest ending balance started in {worst.start_year}; "
        f"the highest started in {best.start_year}."
    )


def _summary(
    rows: list[WithdrawalStrategyResult],
    base_strategy: WithdrawalStrategy,
) -> str:
    """Build a factual, non-advice summary of the comparison."""
    highest_success = max(rows, key=lambda row: row.success_rate)
    lowest_taxes = min(rows, key=lambda row: row.total_taxes_median)
    highest_final = max(rows, key=lambda row: row.median_final_value)

    parts = [
        f"{highest_success.withdrawal_strategy} has the highest modeled success rate ({highest_success.success_rate:.0%}).",
        f"{lowest_taxes.withdrawal_strategy} has the lowest median modeled taxes.",
        f"{highest_final.withdrawal_strategy} has the highest median final portfolio value.",
    ]
    if (
        highest_success.withdrawal_strategy
        == lowest_taxes.withdrawal_strategy
        == highest_final.withdrawal_strategy
    ):
        return (
            f"{highest_success.withdrawal_strategy} leads all three modeled metrics "
            f"relative to the base strategy ({base_strategy})."
        )
    return " ".join(parts)
