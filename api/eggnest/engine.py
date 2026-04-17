"""Engine-first local API for EggNest modeling.

This module gives Python callers, the CLI, and MCP tools a stable interface
to the retirement model without going through FastAPI.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import __version__
from .backtest import run_historical_backtest
from .compensation import analyze_compensation, list_market_benchmarks
from .household import HouseholdCalculator
from .models import (
    AllocationComparisonResult,
    AllocationInput,
    AllocationResult,
    AnnuityComparison,
    AnnuityComparisonResult,
    CompensationAnalysisInput,
    CompensationAnalysisResult,
    CompensationBenchmark,
    EngineResultMetadata,
    HistoricalBacktestInput,
    HistoricalBacktestResult,
    HistoricalRothConversionSummary,
    HistoricalStrategySummary,
    HouseholdInput,
    HouseholdResult,
    LifeEventComparison,
    LifeEventComparisonInput,
    MortalityRates,
    RothConversionComparisonItem,
    RothConversionComparisonResult,
    RothConversionInput,
    RothConversionPolicy,
    RothConversionScenarioSummary,
    RothOptimizationInput,
    RothOptimizationResult,
    SimulationInput,
    SimulationResult,
    SSTimingComparisonResult,
    SSTimingInput,
    SSTimingResult,
    StateComparisonInput,
    StateComparisonResult,
    StateResult,
    StrategyComparisonInput,
    StrategyComparisonItem,
    StrategyComparisonResult,
    StrategyScenarioSummary,
    default_roth_conversion_end_age,
)
from .mortality import calculate_survival_curve, get_mortality_rates
from .returns import get_historical_stats
from .roth_reporting import build_roth_optimization_report_artifact
from .simulation import MonteCarloSimulator, compare_to_annuity
from .ss_timing import calculate_adjusted_benefit, get_full_retirement_age

DEFAULT_COMPARISON_PARALLELISM = 4
METHOD_VERSION = "2026-04-07.engine-contract-v1"
DEFAULT_DYNAMIC_ROTH_POLICIES: tuple[RothConversionPolicy, ...] = (
    "fill_standard_deduction",
    "fill_12_percent_bracket",
    "fill_22_percent_bracket",
)


def _validate_model(payload: Any, model_cls):
    """Accept either already-validated models or plain mappings."""
    if isinstance(payload, model_cls):
        return payload
    return model_cls.model_validate(payload)


def _run_simulation_summary(params_payload: dict[str, Any]) -> dict[str, float | dict[str, float]]:
    """Run a single simulation scenario and return comparison fields."""
    result = _run_simulation_result(params_payload)
    return {
        "success_rate": result.success_rate,
        "median_final_value": result.median_final_value,
        "median_final_value_real": result.median_final_value_real,
        "total_taxes_median": result.total_taxes_median,
        "total_medicare_premiums_median": result.total_medicare_premiums_median,
        "total_withdrawn_median": result.total_withdrawn_median,
        "total_roth_conversions_median": result.total_roth_conversions_median,
        "percentiles": result.percentiles,
    }


def _run_simulation_result(params_payload: dict[str, Any]) -> SimulationResult:
    """Run a single simulation scenario and return the full result."""
    params = SimulationInput.model_validate(params_payload)
    return MonteCarloSimulator(params).run()


def _run_historical_backtest_summary(params_payload: dict[str, Any]) -> dict[str, float | int]:
    """Run one historical backtest scenario and return comparison fields."""
    params = SimulationInput.model_validate(params_payload)
    result = run_historical_backtest(params)
    worst_cohort = min(
        result.results,
        key=lambda cohort: (cohort.final_value_real, cohort.start_year),
    )
    return {
        "success_rate": result.success_rate,
        "median_final_value": result.median_final_value,
        "median_final_value_real": result.median_final_value_real,
        "total_taxes_median": result.total_taxes_median,
        "total_medicare_premiums_median": result.total_medicare_premiums_median,
        "total_withdrawn_median": result.total_withdrawn_median,
        "total_roth_conversions_median": result.total_roth_conversions_median,
        "cohort_count": len(result.start_years),
        "strongest_start_year": result.strongest_start_year,
        "weakest_start_year": result.weakest_start_year,
        "worst_final_value_real": worst_cohort.final_value_real,
    }


def _normalize_metric(values: list[float], *, higher_is_better: bool) -> list[float]:
    """Scale a metric into 0-1 scores for blended ranking."""
    if not values:
        return []
    lower = min(values)
    upper = max(values)
    if abs(upper - lower) < 1e-12:
        return [0.5] * len(values)
    if higher_is_better:
        return [(value - lower) / (upper - lower) for value in values]
    return [(upper - value) / (upper - lower) for value in values]


def _strategy_label(strategy: str) -> str:
    """Humanize a withdrawal strategy enum."""
    return strategy.replace("_", " ").title()


def _roth_conversion_label(amount: float) -> str:
    """Humanize a fixed annual Roth conversion amount."""
    if abs(amount) < 1e-9:
        return "No annual conversion"
    return f"${amount:,.0f} per year"


def _roth_conversion_policy_label(policy: RothConversionPolicy) -> str:
    """Humanize a Roth conversion sizing policy."""
    labels = {
        "fixed_amount": "Fixed annual amount",
        "fill_standard_deduction": "Fill standard deduction",
        "fill_12_percent_bracket": "Fill 12% bracket",
        "fill_22_percent_bracket": "Fill 22% bracket",
    }
    return labels[policy]


def _roth_conversion_scenario_label(
    policy: RothConversionPolicy, amount: float | None = None
) -> str:
    """Build a user-facing label for one Roth conversion scenario."""
    if policy == "fixed_amount":
        if amount is None:
            raise ValueError("Fixed-amount Roth scenarios require an annual amount")
        return _roth_conversion_label(amount)
    return _roth_conversion_policy_label(policy)


def _roth_conversion_window_suffix(start_age: int, end_age: int) -> str:
    """Render a short age-window suffix for Roth search scenarios."""
    if start_age == end_age:
        return f" (age {start_age})"
    return f" (ages {start_age}-{end_age})"


def _default_roth_optimization_start_ages(base_input: SimulationInput) -> list[int]:
    """Choose a bounded set of plausible Roth conversion start ages."""
    anchors = {
        base_input.current_age,
        min(base_input.current_age + 5, base_input.max_age),
        min(base_input.current_age + 10, base_input.max_age),
        default_roth_conversion_end_age(base_input.current_age, base_input.max_age),
    }
    return sorted(
        age
        for age in anchors
        if base_input.current_age <= age <= base_input.max_age
    )


def _build_roth_search_end_ages(
    start_age: int,
    max_age: int,
    window_lengths: list[int],
) -> list[int]:
    """Build bounded end ages for one Roth conversion start age."""
    end_ages = {
        default_roth_conversion_end_age(start_age, max_age),
        *[min(max_age, start_age + length - 1) for length in window_lengths],
    }
    return sorted(end_age for end_age in end_ages if end_age >= start_age)


def _build_roth_optimization_scenarios(
    validated: RothOptimizationInput,
) -> tuple[list[int], list[int], list[dict[str, float | str | int]]]:
    """Expand a bounded Roth search into concrete scenarios."""
    annual_amounts = list(dict.fromkeys(validated.annual_conversion_amounts))
    dynamic_policies = [
        policy
        for policy in dict.fromkeys(validated.conversion_policies)
        if policy != "fixed_amount"
    ]
    start_ages = (
        sorted(dict.fromkeys(validated.candidate_start_ages))
        if validated.candidate_start_ages
        else _default_roth_optimization_start_ages(validated.base_input)
    )
    window_lengths = sorted(dict.fromkeys(validated.window_lengths))

    scenarios: list[dict[str, float | str | int]] = [
        {
            "policy": "fixed_amount",
            "amount": 0.0,
            "label": _roth_conversion_scenario_label("fixed_amount", 0),
            "start_age": validated.base_input.current_age,
            "end_age": default_roth_conversion_end_age(
                validated.base_input.current_age,
                validated.base_input.max_age,
            ),
        }
    ]
    seen = {
        (
            "fixed_amount",
            0.0,
            validated.base_input.current_age,
            default_roth_conversion_end_age(
                validated.base_input.current_age,
                validated.base_input.max_age,
            ),
        )
    }

    for start_age in start_ages:
        for end_age in _build_roth_search_end_ages(
            start_age,
            validated.base_input.max_age,
            window_lengths,
        ):
            for amount in annual_amounts:
                if abs(amount) < 1e-9:
                    continue
                key = ("fixed_amount", amount, start_age, end_age)
                if key in seen:
                    continue
                seen.add(key)
                scenarios.append(
                    {
                        "policy": "fixed_amount",
                        "amount": amount,
                        "label": (
                            _roth_conversion_scenario_label("fixed_amount", amount)
                            + _roth_conversion_window_suffix(start_age, end_age)
                        ),
                        "start_age": start_age,
                        "end_age": end_age,
                    }
                )
            for policy in dynamic_policies:
                key = (policy, 0.0, start_age, end_age)
                if key in seen:
                    continue
                seen.add(key)
                scenarios.append(
                    {
                        "policy": policy,
                        "amount": 0.0,
                        "label": (
                            _roth_conversion_scenario_label(policy)
                            + _roth_conversion_window_suffix(start_age, end_age)
                        ),
                        "start_age": start_age,
                        "end_age": end_age,
                    }
                )

    if len(scenarios) > validated.max_candidates:
        raise ValueError(
            "Roth conversion optimization generated too many candidates; "
            "narrow the start ages, window lengths, or amount/policy list"
        )

    return start_ages, window_lengths, scenarios


def _select_roth_conversion_baseline_index(
    scenarios: list[dict[str, float | str]],
) -> int:
    """Pick the scenario used for Roth-comparison deltas."""
    zero_conversion_index = next(
        (
            index
            for index, scenario in enumerate(scenarios)
            if scenario["policy"] == "fixed_amount" and float(scenario["amount"]) == 0
        ),
        None,
    )
    if zero_conversion_index is not None:
        return zero_conversion_index

    fixed_amount_candidates = [
        (index, float(scenario["amount"]))
        for index, scenario in enumerate(scenarios)
        if scenario["policy"] == "fixed_amount"
    ]
    if fixed_amount_candidates:
        return min(fixed_amount_candidates, key=lambda candidate: candidate[1])[0]

    return 0


def _apply_roth_yearly_baseline_deltas(
    item: RothConversionComparisonItem,
    baseline_item: RothConversionComparisonItem,
) -> RothConversionComparisonItem:
    """Annotate one Roth scenario's representative path with baseline deltas."""
    baseline_rows = baseline_item.monte_carlo.year_breakdown
    updated_rows = []
    for index, row in enumerate(item.monte_carlo.year_breakdown):
        baseline_total = 0.0
        if index < len(baseline_rows):
            baseline_total = baseline_rows[index].medicare_total_premium
        updated_rows.append(
            row.model_copy(
                update={
                    "medicare_premium_delta_vs_baseline": (
                        row.medicare_total_premium - baseline_total
                    )
                }
            )
        )

    return item.model_copy(
        update={
            "monte_carlo": item.monte_carlo.model_copy(
                update={"year_breakdown": updated_rows}
            )
        }
    )


def _build_result_metadata(
    *,
    random_seed: int | None,
    assumptions_summary: str,
) -> EngineResultMetadata:
    """Construct a standard metadata block for engine-facing results."""
    return EngineResultMetadata(
        engine_version=__version__,
        method_version=METHOD_VERSION,
        random_seed=random_seed,
        assumptions_summary=assumptions_summary,
    )


def _attach_metadata(result: Any, *, random_seed: int | None, assumptions_summary: str):
    """Stamp one Pydantic result model with reproducibility metadata."""
    return result.model_copy(
        update={
            "metadata": _build_result_metadata(
                random_seed=random_seed,
                assumptions_summary=assumptions_summary,
            )
        }
    )


def _summarize_simulation_input(
    sim_input: SimulationInput,
    *,
    extra_parts: list[str] | None = None,
) -> str:
    """Summarize the main modeled assumptions for one retirement scenario."""
    parts = [
        f"{sim_input.return_model} returns",
        f"{sim_input.inflation_model} inflation",
        f"{sim_input.spending_mode} spending",
        f"{sim_input.state} / {sim_input.filing_status}",
        (
            "holdings-based portfolio"
            if sim_input.holdings
            else f"{int(sim_input.stock_allocation * 100)}% stocks / "
            f"{int((1 - sim_input.stock_allocation) * 100)}% bonds"
        ),
    ]
    if extra_parts:
        parts.extend(extra_parts)
    return ", ".join(parts)


def _summarize_household_input(household: HouseholdInput) -> str:
    """Summarize a household tax calculation request."""
    parts = [
        f"{household.year} {household.state} household",
        household.filing_status,
        f"{len(household.people)} people",
    ]
    if household.countable_cash_assets > 0:
        parts.append(f"${household.countable_cash_assets:,.0f} countable cash assets")
    if any(person.roth_conversion_amount > 0 for person in household.people):
        parts.append("includes Roth conversion income")
    return ", ".join(parts)


def _summarize_compensation_input(input_data: CompensationAnalysisInput) -> str:
    """Summarize one employer-side compensation analysis request."""
    return (
        f"{len(input_data.packages)} package(s), "
        f"{input_data.employee_profile.state} / "
        f"{input_data.employee_profile.filing_status} employee profile"
    )


def _calculate_blended_scores(
    monte_carlo_summaries: list[dict[str, float | dict[str, float]]],
    historical_summaries: list[dict[str, float | int]],
) -> list[float]:
    """Blend Monte Carlo and historical metrics into a 0-100 comparison score."""
    mc_success_scores = _normalize_metric(
        [float(summary["success_rate"]) for summary in monte_carlo_summaries],
        higher_is_better=True,
    )
    historical_success_scores = _normalize_metric(
        [float(summary["success_rate"]) for summary in historical_summaries],
        higher_is_better=True,
    )
    worst_cohort_scores = _normalize_metric(
        [float(summary["worst_final_value_real"]) for summary in historical_summaries],
        higher_is_better=True,
    )
    mc_real_wealth_scores = _normalize_metric(
        [float(summary["median_final_value_real"]) for summary in monte_carlo_summaries],
        higher_is_better=True,
    )
    tax_efficiency_scores = _normalize_metric(
        [float(summary["total_taxes_median"]) for summary in monte_carlo_summaries],
        higher_is_better=False,
    )

    return [
        round(
            100
            * (
                mc_success_scores[index] * 0.35
                + historical_success_scores[index] * 0.35
                + worst_cohort_scores[index] * 0.15
                + mc_real_wealth_scores[index] * 0.10
                + tax_efficiency_scores[index] * 0.05
            ),
            1,
        )
        for index in range(len(monte_carlo_summaries))
    ]


def _evaluate_roth_conversion_scenarios(
    *,
    base_input: SimulationInput,
    scenarios: list[dict[str, float | str | int]],
    namespace: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run Monte Carlo and historical summaries for a set of Roth scenarios."""
    comparison_seed = _resolve_comparison_seed(
        base_input,
        namespace=namespace,
        payload=payload,
    )
    scenario_inputs = [
        base_input.model_copy(
            update={
                "roth_conversion_policy": scenario["policy"],
                "roth_conversion_amount": scenario["amount"],
                "roth_conversion_start_age": scenario["start_age"],
                "roth_conversion_end_age": scenario["end_age"],
                "random_seed": comparison_seed,
            }
        )
        for scenario in scenarios
    ]
    monte_carlo_results = [
        _run_simulation_result(sim_input.model_dump(mode="python"))
        for sim_input in scenario_inputs
    ]
    monte_carlo_summaries = [
        {
            "success_rate": result.success_rate,
            "median_final_value": result.median_final_value,
            "median_final_value_real": result.median_final_value_real,
            "total_taxes_median": result.total_taxes_median,
            "total_medicare_premiums_median": result.total_medicare_premiums_median,
            "total_withdrawn_median": result.total_withdrawn_median,
            "total_roth_conversions_median": result.total_roth_conversions_median,
        }
        for result in monte_carlo_results
    ]
    historical_summaries = [
        _run_historical_backtest_summary(sim_input.model_dump(mode="python"))
        for sim_input in scenario_inputs
    ]
    blended_scores = _calculate_blended_scores(
        monte_carlo_summaries, historical_summaries
    )

    results: list[RothConversionComparisonItem] = []
    for index, (scenario, monte_carlo, monte_carlo_result, historical) in enumerate(
        zip(
            scenarios,
            monte_carlo_summaries,
            monte_carlo_results,
            historical_summaries,
            strict=True,
        )
    ):
        results.append(
            RothConversionComparisonItem(
                conversion_policy=scenario["policy"],
                scenario_label=scenario["label"],
                annual_conversion_amount=(
                    float(scenario["amount"])
                    if scenario["policy"] == "fixed_amount"
                    else None
                ),
                conversion_start_age=int(scenario["start_age"]),
                conversion_end_age=int(scenario["end_age"]),
                monte_carlo=RothConversionScenarioSummary(
                    success_rate=monte_carlo["success_rate"],
                    median_final_value=monte_carlo["median_final_value"],
                    median_final_value_real=monte_carlo["median_final_value_real"],
                    total_taxes_median=monte_carlo["total_taxes_median"],
                    total_medicare_premiums_median=monte_carlo[
                        "total_medicare_premiums_median"
                    ],
                    total_withdrawn_median=monte_carlo["total_withdrawn_median"],
                    total_roth_conversions_median=monte_carlo[
                        "total_roth_conversions_median"
                    ],
                    year_breakdown=monte_carlo_result.year_breakdown,
                ),
                historical=HistoricalRothConversionSummary(
                    success_rate=historical["success_rate"],
                    median_final_value=historical["median_final_value"],
                    median_final_value_real=historical["median_final_value_real"],
                    total_taxes_median=historical["total_taxes_median"],
                    total_medicare_premiums_median=historical[
                        "total_medicare_premiums_median"
                    ],
                    total_withdrawn_median=historical["total_withdrawn_median"],
                    total_roth_conversions_median=historical[
                        "total_roth_conversions_median"
                    ],
                    cohort_count=historical["cohort_count"],
                    strongest_start_year=historical["strongest_start_year"],
                    weakest_start_year=historical["weakest_start_year"],
                    worst_final_value_real=historical["worst_final_value_real"],
                ),
                blended_score=blended_scores[index],
            )
        )

    baseline_index = _select_roth_conversion_baseline_index(scenarios)
    baseline_result = results[baseline_index]
    baseline_label = baseline_result.scenario_label
    baseline_amount = baseline_result.annual_conversion_amount

    updated_results: list[RothConversionComparisonItem] = []
    for item in results:
        item.delta_vs_baseline.blended_score_delta = (
            item.blended_score - baseline_result.blended_score
        )
        item.delta_vs_baseline.monte_carlo_success_rate_delta = (
            item.monte_carlo.success_rate - baseline_result.monte_carlo.success_rate
        )
        item.delta_vs_baseline.historical_success_rate_delta = (
            item.historical.success_rate - baseline_result.historical.success_rate
        )
        item.delta_vs_baseline.monte_carlo_median_final_value_real_delta = (
            item.monte_carlo.median_final_value_real
            - baseline_result.monte_carlo.median_final_value_real
        )
        item.delta_vs_baseline.historical_median_final_value_real_delta = (
            item.historical.median_final_value_real
            - baseline_result.historical.median_final_value_real
        )
        item.delta_vs_baseline.monte_carlo_total_taxes_median_delta = (
            item.monte_carlo.total_taxes_median
            - baseline_result.monte_carlo.total_taxes_median
        )
        item.delta_vs_baseline.monte_carlo_total_medicare_premiums_median_delta = (
            item.monte_carlo.total_medicare_premiums_median
            - baseline_result.monte_carlo.total_medicare_premiums_median
        )
        item.delta_vs_baseline.monte_carlo_total_roth_conversions_median_delta = (
            item.monte_carlo.total_roth_conversions_median
            - baseline_result.monte_carlo.total_roth_conversions_median
        )
        item.delta_vs_baseline.historical_total_medicare_premiums_median_delta = (
            item.historical.total_medicare_premiums_median
            - baseline_result.historical.total_medicare_premiums_median
        )
        item.delta_vs_baseline.historical_worst_final_value_real_delta = (
            item.historical.worst_final_value_real
            - baseline_result.historical.worst_final_value_real
        )
        updated_results.append(_apply_roth_yearly_baseline_deltas(item, baseline_result))

    results = updated_results

    top_scoring = max(
        results,
        key=lambda result: (
            result.blended_score,
            result.historical.success_rate,
            result.monte_carlo.success_rate,
            result.historical.worst_final_value_real,
        ),
    )
    lowest_modeled_tax = min(
        results,
        key=lambda result: (
            result.monte_carlo.total_taxes_median,
            -result.monte_carlo.success_rate,
        ),
    )
    strongest_historical = max(
        results,
        key=lambda result: (
            result.historical.success_rate,
            result.historical.worst_final_value_real,
            result.historical.median_final_value_real,
        ),
    )
    lowest_medicare_premium = min(
        results,
        key=lambda result: (
            result.monte_carlo.total_medicare_premiums_median,
            result.monte_carlo.total_taxes_median,
        ),
    )
    highest_real_ending_wealth = max(
        results,
        key=lambda result: (
            result.monte_carlo.median_final_value_real,
            result.historical.median_final_value_real,
            -result.monte_carlo.total_taxes_median,
        ),
    )

    summary_parts = [
        (
            f"{top_scoring.scenario_label} is the current score leader after weighting "
            "Monte Carlo success at 35%, historical success at 35%, weakest "
            "historical cohort at 15%, median real ending wealth at 10%, and "
            "lower modeled taxes at 5%."
        )
    ]
    if baseline_label != top_scoring.scenario_label:
        summary_parts.append(
            f"Deltas are measured against {baseline_label} as the baseline scenario."
        )
    if lowest_modeled_tax.scenario_label != top_scoring.scenario_label:
        summary_parts.append(
            f"{lowest_modeled_tax.scenario_label} shows the lowest modeled median taxes."
        )
    if strongest_historical.scenario_label != top_scoring.scenario_label:
        summary_parts.append(
            f"{strongest_historical.scenario_label} leads on historical resilience."
        )

    results.sort(key=lambda result: result.blended_score, reverse=True)

    return {
        "comparison_seed": comparison_seed,
        "results": results,
        "baseline_label": baseline_label,
        "baseline_amount": baseline_amount,
        "top_scoring": top_scoring,
        "lowest_modeled_tax": lowest_modeled_tax,
        "strongest_historical": strongest_historical,
        "lowest_medicare_premium": lowest_medicare_premium,
        "highest_real_ending_wealth": highest_real_ending_wealth,
        "summary": " ".join(summary_parts),
    }


def _derive_comparison_seed(namespace: str, payload: dict[str, Any]) -> int:
    """Generate a stable seed for comparison scenarios when the caller did not supply one."""
    digest = hashlib.sha256(
        json.dumps({"namespace": namespace, "payload": payload}, sort_keys=True).encode(
            "utf-8"
        )
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _resolve_comparison_seed(
    base_input: SimulationInput, *, namespace: str, payload: dict[str, Any]
) -> int:
    """Use the caller-provided seed when present, otherwise derive a stable comparison seed."""
    if base_input.random_seed is not None:
        return base_input.random_seed
    return _derive_comparison_seed(namespace, payload)


def describe_engine() -> dict[str, Any]:
    """Describe the local EggNest engine surface for Python and MCP consumers."""
    return {
        "name": "EggNest",
        "version": __version__,
        "method_version": METHOD_VERSION,
        "python_package": "eggnest",
        "capabilities": [
            "simulate",
            "historical_backtest",
            "compare_withdrawal_strategies",
            "compare_roth_conversions",
            "optimize_roth_conversions",
            "optimize_roth_conversions_report",
            "compare_allocations",
            "compare_social_security_timing",
            "calculate_household",
            "compare_life_event",
            "analyze_compensation",
        ],
        "notes": [
            "CLI, MCP, and the web API are clients of the same local model layer.",
            "Comparison calls derive a stable random seed when the caller does not supply one.",
        ],
    }


class EggnestEngine:
    """Stable local entrypoint for EggNest modeling."""

    def __init__(self, parallelism: int = DEFAULT_COMPARISON_PARALLELISM):
        self.parallelism = parallelism

    def simulate(self, params: SimulationInput | dict[str, Any]) -> SimulationResult:
        """Run a Monte Carlo simulation locally."""
        validated = _validate_model(params, SimulationInput)
        result = MonteCarloSimulator(validated).run()
        return _attach_metadata(
            result,
            random_seed=validated.random_seed,
            assumptions_summary=_summarize_simulation_input(validated),
        )

    def simulate_with_progress(self, params: SimulationInput | dict[str, Any]):
        """Yield progress events from a local simulation run."""
        validated = _validate_model(params, SimulationInput)
        simulator = MonteCarloSimulator(validated)
        for event in simulator.run_with_progress():
            if event["type"] == "complete":
                event["result"] = _attach_metadata(
                    SimulationResult.model_validate(event["result"]),
                    random_seed=validated.random_seed,
                    assumptions_summary=_summarize_simulation_input(validated),
                ).model_dump(mode="json")
            yield event

    def historical_backtest(
        self, input_data: HistoricalBacktestInput | dict[str, Any]
    ) -> HistoricalBacktestResult:
        """Replay the model over exact historical retirement cohorts."""
        validated = _validate_model(input_data, HistoricalBacktestInput)
        result = run_historical_backtest(validated)
        return _attach_metadata(
            result,
            random_seed=validated.base_input.random_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[
                    (
                        f"{len(validated.start_years)} explicit start years"
                        if validated.start_years is not None
                        else "full historical cohort sweep"
                    )
                ],
            ),
        )

    def compare_annuity(
        self, comparison: AnnuityComparison | dict[str, Any]
    ) -> AnnuityComparisonResult:
        """Compare a simulation to an annuity option."""
        validated = _validate_model(comparison, AnnuityComparison)
        simulator = MonteCarloSimulator(validated.simulation_input)
        sim_result = _attach_metadata(
            simulator.run(),
            random_seed=validated.simulation_input.random_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.simulation_input,
                extra_parts=[
                    f"annuity ${validated.annuity_monthly_payment:,.0f}/mo",
                    f"{validated.annuity_guarantee_years}-year guarantee",
                ],
            ),
        )

        n_years = (
            validated.simulation_input.max_age - validated.simulation_input.current_age
        )
        annuity_comparison = compare_to_annuity(
            simulation_result=sim_result,
            annuity_monthly_payment=validated.annuity_monthly_payment,
            annuity_guarantee_years=validated.annuity_guarantee_years,
            n_years=n_years,
            total_withdrawn=simulator._total_withdrawn,
            total_taxes=simulator._total_taxes,
            total_medicare_premiums=getattr(
                simulator, "_total_medicare_premiums", None
            ),
        )

        return _attach_metadata(
            AnnuityComparisonResult(
            simulation_result=sim_result,
            annuity_total_guaranteed=annuity_comparison["annuity_total_guaranteed"],
            probability_simulation_beats_annuity=annuity_comparison[
                "probability_simulation_beats_annuity"
            ],
            simulation_median_total_income=annuity_comparison[
                "simulation_median_total_income"
            ],
            summary=annuity_comparison["summary"],
            ),
            random_seed=validated.simulation_input.random_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.simulation_input,
                extra_parts=[
                    f"annuity ${validated.annuity_monthly_payment:,.0f}/mo",
                    f"{validated.annuity_guarantee_years}-year guarantee",
                ],
            ),
        )

    def compare_withdrawal_strategies(
        self, comparison: StrategyComparisonInput | dict[str, Any]
    ) -> StrategyComparisonResult:
        """Compare tax-aware withdrawal strategies under the same assumptions."""
        validated = _validate_model(comparison, StrategyComparisonInput)
        if not validated.base_input.holdings:
            raise ValueError(
                "Withdrawal strategy comparison requires detailed holdings. "
                "Add account-level holdings first."
            )

        strategies = list(dict.fromkeys(validated.strategies))
        comparison_seed = _resolve_comparison_seed(
            validated.base_input,
            namespace="compare-withdrawal-strategies",
            payload={
                "base_input": validated.base_input.model_dump(mode="json"),
                "strategies": strategies,
            },
        )

        strategy_inputs = [
            validated.base_input.model_copy(
                update={"withdrawal_strategy": strategy, "random_seed": comparison_seed}
            )
            for strategy in strategies
        ]
        monte_carlo_summaries = [
            _run_simulation_summary(sim_input.model_dump(mode="python"))
            for sim_input in strategy_inputs
        ]
        historical_summaries = [
            _run_historical_backtest_summary(sim_input.model_dump(mode="python"))
            for sim_input in strategy_inputs
        ]

        blended_scores = _calculate_blended_scores(
            monte_carlo_summaries, historical_summaries
        )

        strategy_results: list[StrategyComparisonItem] = []
        for index, (strategy, monte_carlo, historical) in enumerate(
            zip(strategies, monte_carlo_summaries, historical_summaries, strict=True)
        ):
            strategy_results.append(
                StrategyComparisonItem(
                    strategy=strategy,
                    monte_carlo=StrategyScenarioSummary(
                        success_rate=monte_carlo["success_rate"],
                        median_final_value=monte_carlo["median_final_value"],
                        median_final_value_real=monte_carlo["median_final_value_real"],
                        total_taxes_median=monte_carlo["total_taxes_median"],
                        total_medicare_premiums_median=monte_carlo[
                            "total_medicare_premiums_median"
                        ],
                        total_withdrawn_median=monte_carlo["total_withdrawn_median"],
                    ),
                    historical=HistoricalStrategySummary(
                        success_rate=historical["success_rate"],
                        median_final_value=historical["median_final_value"],
                        median_final_value_real=historical["median_final_value_real"],
                        total_taxes_median=historical["total_taxes_median"],
                        total_medicare_premiums_median=historical[
                            "total_medicare_premiums_median"
                        ],
                        total_withdrawn_median=historical["total_withdrawn_median"],
                        cohort_count=historical["cohort_count"],
                        strongest_start_year=historical["strongest_start_year"],
                        weakest_start_year=historical["weakest_start_year"],
                        worst_final_value_real=historical["worst_final_value_real"],
                    ),
                    blended_score=blended_scores[index],
                )
            )

        top_scoring = max(
            strategy_results,
            key=lambda result: (
                result.blended_score,
                result.historical.success_rate,
                result.monte_carlo.success_rate,
                result.historical.worst_final_value_real,
            ),
        )
        lowest_modeled_tax = min(
            strategy_results,
            key=lambda result: (
                result.monte_carlo.total_taxes_median,
                -result.monte_carlo.success_rate,
            ),
        )
        strongest_historical = max(
            strategy_results,
            key=lambda result: (
                result.historical.success_rate,
                result.historical.worst_final_value_real,
                result.historical.median_final_value_real,
            ),
        )

        top_scoring_label = _strategy_label(top_scoring.strategy)
        summary_parts = [
            f"{top_scoring_label} leads this scorecard after weighting Monte Carlo success at 35%, historical success at 35%, weakest historical cohort at 15%, median real ending wealth at 10%, and lower modeled taxes at 5%."
        ]
        if lowest_modeled_tax.strategy != top_scoring.strategy:
            summary_parts.append(
                f"{_strategy_label(lowest_modeled_tax.strategy)} posts the lowest modeled median taxes."
            )
        if strongest_historical.strategy != top_scoring.strategy:
            summary_parts.append(
                f"{_strategy_label(strongest_historical.strategy)} leads on historical resilience."
            )

        strategy_results.sort(key=lambda result: result.blended_score, reverse=True)

        return _attach_metadata(
            StrategyComparisonResult(
                results=strategy_results,
                top_scoring_strategy=top_scoring.strategy,
                lowest_modeled_tax_strategy=lowest_modeled_tax.strategy,
                strongest_historical_strategy=strongest_historical.strategy,
                summary=" ".join(summary_parts),
            ),
            random_seed=comparison_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[
                    "withdrawal strategies: "
                    + ", ".join(_strategy_label(strategy) for strategy in strategies)
                ],
            ),
        )

    def compare_roth_conversions(
        self, comparison: RothConversionInput | dict[str, Any]
    ) -> RothConversionComparisonResult:
        """Compare fixed-amount and bracket-fill Roth conversion scenarios."""
        validated = _validate_model(comparison, RothConversionInput)

        annual_amounts = list(dict.fromkeys(validated.annual_conversion_amounts))
        dynamic_policies = [
            policy
            for policy in dict.fromkeys(validated.conversion_policies)
            if policy != "fixed_amount"
        ]
        conversion_start_age = (
            validated.conversion_start_age
            if validated.conversion_start_age is not None
            else validated.base_input.current_age
        )
        conversion_end_age = (
            validated.conversion_end_age
            if validated.conversion_end_age is not None
            else default_roth_conversion_end_age(
                conversion_start_age, validated.base_input.max_age
            )
        )

        scenarios = [
            {
                "policy": "fixed_amount",
                "amount": amount,
                "label": _roth_conversion_scenario_label("fixed_amount", amount),
                "start_age": conversion_start_age,
                "end_age": conversion_end_age,
            }
            for amount in annual_amounts
        ] + [
            {
                "policy": policy,
                "amount": 0.0,
                "label": _roth_conversion_scenario_label(policy),
                "start_age": conversion_start_age,
                "end_age": conversion_end_age,
            }
            for policy in dynamic_policies
        ]
        evaluation = _evaluate_roth_conversion_scenarios(
            base_input=validated.base_input,
            scenarios=scenarios,
            namespace="compare-roth-conversions",
            payload={
                "base_input": validated.base_input.model_dump(mode="json"),
                "annual_conversion_amounts": annual_amounts,
                "conversion_policies": dynamic_policies,
                "conversion_start_age": conversion_start_age,
                "conversion_end_age": conversion_end_age,
            },
        )

        return _attach_metadata(
            RothConversionComparisonResult(
                results=evaluation["results"],
                baseline_scenario_label=evaluation["baseline_label"],
                baseline_conversion_amount=evaluation["baseline_amount"],
                top_scoring_scenario_label=evaluation["top_scoring"].scenario_label,
                top_scoring_conversion_amount=(
                    evaluation["top_scoring"].annual_conversion_amount
                ),
                lowest_modeled_tax_scenario_label=(
                    evaluation["lowest_modeled_tax"].scenario_label
                ),
                lowest_modeled_tax_amount=(
                    evaluation["lowest_modeled_tax"].annual_conversion_amount
                ),
                strongest_historical_scenario_label=(
                    evaluation["strongest_historical"].scenario_label
                ),
                strongest_historical_conversion_amount=(
                    evaluation["strongest_historical"].annual_conversion_amount
                ),
                summary=evaluation["summary"],
            ),
            random_seed=evaluation["comparison_seed"],
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[
                    f"conversion window {conversion_start_age}-{conversion_end_age}",
                    "roth scenarios: "
                    + ", ".join(scenario["label"] for scenario in scenarios),
                ],
            ),
        )

    def optimize_roth_conversions(
        self, optimization: RothOptimizationInput | dict[str, Any]
    ) -> RothOptimizationResult:
        """Search bounded Roth conversion windows, amounts, and policy families."""
        validated = _validate_model(optimization, RothOptimizationInput)
        start_ages, window_lengths, scenarios = _build_roth_optimization_scenarios(
            validated
        )
        evaluation = _evaluate_roth_conversion_scenarios(
            base_input=validated.base_input,
            scenarios=scenarios,
            namespace="optimize-roth-conversions",
            payload={
                "base_input": validated.base_input.model_dump(mode="json"),
                "annual_conversion_amounts": list(
                    dict.fromkeys(validated.annual_conversion_amounts)
                ),
                "conversion_policies": list(dict.fromkeys(validated.conversion_policies)),
                "candidate_start_ages": start_ages,
                "window_lengths": window_lengths,
            },
        )

        summary = (
            f"{evaluation['summary']} "
            f"Searched {len(scenarios)} candidates across start ages "
            f"{', '.join(str(age) for age in start_ages)} and window lengths "
            f"{', '.join(str(length) for length in window_lengths)} years. "
            f"{evaluation['lowest_medicare_premium'].scenario_label} shows the lowest "
            "modeled Medicare premiums. "
            f"{evaluation['highest_real_ending_wealth'].scenario_label} has the "
            "highest Monte Carlo real ending wealth."
        )

        return _attach_metadata(
            RothOptimizationResult(
                results=evaluation["results"],
                baseline_scenario_label=evaluation["baseline_label"],
                baseline_conversion_amount=evaluation["baseline_amount"],
                top_scoring_scenario_label=evaluation["top_scoring"].scenario_label,
                top_scoring_conversion_amount=(
                    evaluation["top_scoring"].annual_conversion_amount
                ),
                lowest_modeled_tax_scenario_label=(
                    evaluation["lowest_modeled_tax"].scenario_label
                ),
                lowest_modeled_tax_amount=(
                    evaluation["lowest_modeled_tax"].annual_conversion_amount
                ),
                strongest_historical_scenario_label=(
                    evaluation["strongest_historical"].scenario_label
                ),
                strongest_historical_conversion_amount=(
                    evaluation["strongest_historical"].annual_conversion_amount
                ),
                candidate_count=len(scenarios),
                candidate_start_ages=start_ages,
                window_lengths=window_lengths,
                lowest_medicare_premium_scenario_label=(
                    evaluation["lowest_medicare_premium"].scenario_label
                ),
                lowest_medicare_premium_conversion_amount=(
                    evaluation["lowest_medicare_premium"].annual_conversion_amount
                ),
                highest_real_ending_wealth_scenario_label=(
                    evaluation["highest_real_ending_wealth"].scenario_label
                ),
                highest_real_ending_wealth_conversion_amount=(
                    evaluation["highest_real_ending_wealth"].annual_conversion_amount
                ),
                summary=summary,
            ),
            random_seed=evaluation["comparison_seed"],
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[
                    "roth optimization search over "
                    + ", ".join(scenario["label"] for scenario in scenarios),
                ],
            ),
        )

    def optimize_roth_conversions_report(
        self, optimization: RothOptimizationInput | dict[str, Any]
    ):
        """Run Roth optimization and return an export-friendly report artifact."""
        result = self.optimize_roth_conversions(optimization)
        return build_roth_optimization_report_artifact(result)

    def compare_states(
        self, comparison: StateComparisonInput | dict[str, Any]
    ) -> StateComparisonResult:
        """Compare modeled outcomes across states."""
        validated = _validate_model(comparison, StateComparisonInput)
        base_state = validated.base_input.state
        all_states = [base_state] + [
            state for state in validated.compare_states if state != base_state
        ]
        comparison_seed = _resolve_comparison_seed(
            validated.base_input,
            namespace="compare-states",
            payload={
                "base_input": validated.base_input.model_dump(mode="json"),
                "states": all_states,
            },
        )
        state_inputs = [
            validated.base_input.model_copy(
                update={"state": state, "random_seed": comparison_seed}
            )
            for state in all_states
        ]
        sim_results = [
            _run_simulation_summary(sim_input.model_dump(mode="python"))
            for sim_input in state_inputs
        ]

        results: list[StateResult] = []
        base_taxes = 0.0

        for state, sim_result in zip(all_states, sim_results, strict=True):
            net_after_tax = (
                sim_result["total_withdrawn_median"] - sim_result["total_taxes_median"]
            )
            result = StateResult(
                state=state,
                success_rate=sim_result["success_rate"],
                median_final_value=sim_result["median_final_value"],
                total_taxes_median=sim_result["total_taxes_median"],
                total_withdrawn_median=sim_result["total_withdrawn_median"],
                net_after_tax_median=net_after_tax,
            )
            results.append(result)
            if state == base_state:
                base_taxes = sim_result["total_taxes_median"]

        tax_savings = {result.state: base_taxes - result.total_taxes_median for result in results}
        return _attach_metadata(
            StateComparisonResult(
                base_state=base_state,
                results=results,
                tax_savings_vs_base=tax_savings,
            ),
            random_seed=comparison_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[f"state comparison: {', '.join(all_states)}"],
            ),
        )

    def compare_ss_timing(
        self, timing_input: SSTimingInput | dict[str, Any]
    ) -> SSTimingComparisonResult:
        """Compare Social Security claiming ages."""
        validated = _validate_model(timing_input, SSTimingInput)
        birth_year = validated.birth_year
        pia_monthly = validated.pia_monthly
        fra = get_full_retirement_age(birth_year)
        comparison_seed = _resolve_comparison_seed(
            validated.base_input,
            namespace="compare-ss-timing",
            payload={
                "base_input": validated.base_input.model_dump(mode="json"),
                "birth_year": birth_year,
                "pia_monthly": pia_monthly,
                "claiming_ages": sorted(validated.claiming_ages),
            },
        )

        claim_inputs: list[tuple[int, float, float, float, SimulationInput]] = []
        result_62_ss_income = 0.0
        for claiming_age in sorted(validated.claiming_ages):
            monthly_benefit = calculate_adjusted_benefit(
                pia_monthly=pia_monthly,
                birth_year=birth_year,
                claiming_age=claiming_age,
            )
            annual_benefit = monthly_benefit * 12
            adjustment_factor = monthly_benefit / pia_monthly
            sim_input = validated.base_input.model_copy(
                update={
                    "social_security_monthly": monthly_benefit,
                    "social_security_start_age": claiming_age,
                    "random_seed": comparison_seed,
                }
            )
            claim_inputs.append(
                (
                    claiming_age,
                    monthly_benefit,
                    annual_benefit,
                    adjustment_factor,
                    sim_input,
                )
            )

        sim_results = [
            _run_simulation_summary(sim_input.model_dump(mode="python"))
            for *_, sim_input in claim_inputs
        ]

        results: list[SSTimingResult] = []
        for (
            claiming_age,
            monthly_benefit,
            annual_benefit,
            adjustment_factor,
            _sim_input,
        ), sim_result in zip(claim_inputs, sim_results, strict=True):
            years_receiving_ss = max(0, validated.base_input.max_age - claiming_age)
            total_ss_income = annual_benefit * years_receiving_ss

            breakeven_vs_62 = None
            if claiming_age == 62:
                result_62_ss_income = total_ss_income
            elif claiming_age > 62 and result_62_ss_income > 0:
                benefit_62 = calculate_adjusted_benefit(pia_monthly, birth_year, 62) * 12
                benefit_this = annual_benefit
                if benefit_this > benefit_62:
                    numerator = 62 * benefit_62 - claiming_age * benefit_this
                    denominator = benefit_62 - benefit_this
                    if denominator != 0:
                        breakeven_age = numerator / denominator
                        if breakeven_age > claiming_age:
                            breakeven_vs_62 = int(round(breakeven_age))

            results.append(
                SSTimingResult(
                    claiming_age=claiming_age,
                    monthly_benefit=round(monthly_benefit, 2),
                    annual_benefit=round(annual_benefit, 2),
                    adjustment_factor=round(adjustment_factor, 4),
                    success_rate=sim_result["success_rate"],
                    median_final_value=sim_result["median_final_value"],
                    total_ss_income_median=round(total_ss_income, 2),
                    total_taxes_median=sim_result["total_taxes_median"],
                    breakeven_vs_62=breakeven_vs_62,
                )
            )

        highest_success = max(results, key=lambda result: result.success_rate)
        highest_lifetime_income = max(
            results, key=lambda result: result.total_ss_income_median
        )

        return _attach_metadata(
            SSTimingComparisonResult(
                birth_year=birth_year,
                full_retirement_age=fra,
                pia_monthly=pia_monthly,
                results=results,
                highest_success_claiming_age=highest_success.claiming_age,
                highest_lifetime_income_claiming_age=highest_lifetime_income.claiming_age,
            ),
            random_seed=comparison_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[
                    f"social security PIA ${pia_monthly:,.0f}/mo",
                    "claiming ages: " + ", ".join(str(age) for age in sorted(validated.claiming_ages)),
                ],
            ),
        )

    def compare_allocations(
        self, allocation_input: AllocationInput | dict[str, Any]
    ) -> AllocationComparisonResult:
        """Compare modeled outcomes across asset allocations."""
        validated = _validate_model(allocation_input, AllocationInput)
        results: list[AllocationResult] = []
        historical_stats = get_historical_stats()
        allocations = sorted(validated.allocations)
        comparison_seed = _resolve_comparison_seed(
            validated.base_input,
            namespace="compare-allocations",
            payload={
                "base_input": validated.base_input.model_dump(mode="json"),
                "allocations": allocations,
            },
        )
        alloc_inputs = [
            validated.base_input.model_copy(
                update={"stock_allocation": stock_alloc, "random_seed": comparison_seed}
            )
            for stock_alloc in allocations
        ]
        sim_results = [
            _run_simulation_summary(sim_input.model_dump(mode="python"))
            for sim_input in alloc_inputs
        ]

        for stock_alloc, sim_result in zip(allocations, sim_results, strict=True):
            bond_alloc = 1.0 - stock_alloc
            expected_return = (
                stock_alloc * historical_stats["stock_mean"]
                + bond_alloc * historical_stats["bond_mean"]
            )
            volatility = (
                stock_alloc * historical_stats["stock_std"]
                + bond_alloc * historical_stats["bond_std"]
            )
            results.append(
                AllocationResult(
                    stock_allocation=stock_alloc,
                    bond_allocation=bond_alloc,
                    success_rate=sim_result["success_rate"],
                    median_final_value=sim_result["median_final_value"],
                    percentile_5_final_value=sim_result["percentiles"]["p5"],
                    percentile_95_final_value=sim_result["percentiles"]["p95"],
                    volatility=round(volatility, 4),
                    expected_return=round(expected_return, 4),
                )
            )

        highest_success = max(results, key=lambda result: result.success_rate)
        high_success_results = [result for result in results if result.success_rate >= 0.8]
        if high_success_results:
            highest_safety = min(high_success_results, key=lambda result: result.volatility)
        else:
            highest_safety = min(results, key=lambda result: result.volatility)

        if highest_success.success_rate >= 0.9:
            if highest_success.stock_allocation == highest_safety.stock_allocation:
                summary = (
                    f"{int(highest_success.stock_allocation * 100)}% stocks delivers both "
                    f"the highest modeled success rate ({highest_success.success_rate:.0%}) "
                    "and the strongest safety profile in this comparison set."
                )
            else:
                summary = (
                    f"{int(highest_success.stock_allocation * 100)}% stocks delivers the "
                    f"highest modeled success ({highest_success.success_rate:.0%}), while "
                    f"{int(highest_safety.stock_allocation * 100)}% stocks shows the lowest "
                    "volatility among the stronger outcomes."
                )
        elif highest_success.success_rate >= 0.8:
            summary = (
                f"{int(highest_success.stock_allocation * 100)}% stocks produces the highest "
                f"modeled success rate in this comparison set at {highest_success.success_rate:.0%}."
            )
        else:
            summary = "All tested allocations produce lower modeled success rates in this comparison set."

        return _attach_metadata(
            AllocationComparisonResult(
                results=results,
                highest_success_allocation=highest_success.stock_allocation,
                highest_safety_allocation=highest_safety.stock_allocation,
                summary=summary,
            ),
            random_seed=comparison_seed,
            assumptions_summary=_summarize_simulation_input(
                validated.base_input,
                extra_parts=[
                    "allocations: "
                    + ", ".join(f"{int(allocation * 100)}%" for allocation in allocations)
                ],
            ),
        )

    def get_mortality(
        self, gender: str, *, start_age: int = 65, end_age: int = 100
    ) -> MortalityRates:
        """Return mortality rates and a survival curve for one gender."""
        if gender not in {"male", "female"}:
            raise ValueError("Gender must be 'male' or 'female'")

        mortality_rates = get_mortality_rates(gender)
        ages = list(range(start_age, end_age + 1))
        rates = [
            mortality_rates.get(
                age, mortality_rates[max(key for key in mortality_rates if key <= age)]
            )
            for age in ages
        ]
        survival = calculate_survival_curve(start_age, end_age + 1, gender)
        return MortalityRates(ages=ages, rates=rates, survival_curve=survival)

    def calculate_household(
        self, household: HouseholdInput | dict[str, Any]
    ) -> HouseholdResult:
        """Calculate taxes and benefits for one household."""
        validated = _validate_model(household, HouseholdInput)
        calculator = HouseholdCalculator()
        return _attach_metadata(
            calculator.calculate(validated),
            random_seed=None,
            assumptions_summary=_summarize_household_input(validated),
        )

    def compare_life_event(
        self, comparison: LifeEventComparisonInput | dict[str, Any]
    ) -> LifeEventComparison:
        """Compare taxes and benefits before and after a household change."""
        validated = _validate_model(comparison, LifeEventComparisonInput)
        calculator = HouseholdCalculator()
        result = calculator.compare(
            validated.before, validated.after, validated.event_name
        )
        return _attach_metadata(
            result.model_copy(
                update={
                    "before_result": _attach_metadata(
                        result.before_result,
                        random_seed=None,
                        assumptions_summary=_summarize_household_input(validated.before),
                    ),
                    "after_result": _attach_metadata(
                        result.after_result,
                        random_seed=None,
                        assumptions_summary=_summarize_household_input(validated.after),
                    ),
                }
            ),
            random_seed=None,
            assumptions_summary=(
                f"{validated.event_name}: "
                f"{_summarize_household_input(validated.before)} -> "
                f"{_summarize_household_input(validated.after)}"
            ),
        )

    def list_market_benchmarks(self) -> list[CompensationBenchmark]:
        """List available employer benchmark rows."""
        return list_market_benchmarks()

    def analyze_compensation(
        self, input_data: CompensationAnalysisInput | dict[str, Any]
    ) -> list[CompensationAnalysisResult]:
        """Analyze employer package design and employee after-tax value."""
        validated = _validate_model(input_data, CompensationAnalysisInput)
        assumptions_summary = _summarize_compensation_input(validated)
        return [
            _attach_metadata(
                result,
                random_seed=None,
                assumptions_summary=f"{assumptions_summary}, package {result.package.name}",
            )
            for result in analyze_compensation(validated)
        ]


_default_engine: EggnestEngine | None = None


def get_engine() -> EggnestEngine:
    """Return a process-local default engine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = EggnestEngine()
    return _default_engine
