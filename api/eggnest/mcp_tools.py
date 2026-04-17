"""Pure tool wrappers for exposing EggNest through MCP."""

from __future__ import annotations

from typing import Any

from .engine import describe_engine, get_engine
from .models import (
    AllocationInput,
    CompensationAnalysisInput,
    HistoricalBacktestInput,
    HouseholdInput,
    LifeEventComparisonInput,
    RothConversionInput,
    RothOptimizationInput,
    SSTimingInput,
    StrategyComparisonInput,
)
from .roth_reporting import build_roth_optimization_report_artifact


def describe_engine_tool() -> dict[str, Any]:
    """Describe the EggNest engine surface."""
    return describe_engine()


def simulate_plan(input_data: dict[str, Any]) -> dict[str, Any]:
    """Run a Monte Carlo simulation from a raw payload."""
    return get_engine().simulate(input_data).model_dump(mode="json")


def historical_backtest_tool(
    base_input: dict[str, Any],
    start_years: list[int] | None = None,
) -> dict[str, Any]:
    """Replay one plan across deterministic historical cohorts."""
    request = HistoricalBacktestInput(base_input=base_input, start_years=start_years)
    return get_engine().historical_backtest(request).model_dump(mode="json")


def compare_withdrawal_strategies_tool(
    base_input: dict[str, Any],
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    """Compare withdrawal strategies for one detailed-holdings plan."""
    request = StrategyComparisonInput(
        base_input=base_input,
        strategies=strategies or ["taxable_first", "traditional_first", "roth_first", "pro_rata"],
    )
    return get_engine().compare_withdrawal_strategies(request).model_dump(mode="json")


def compare_roth_conversions_tool(
    base_input: dict[str, Any],
    annual_conversion_amounts: list[float] | None = None,
    conversion_policies: list[str] | None = None,
    conversion_start_age: int | None = None,
    conversion_end_age: int | None = None,
) -> dict[str, Any]:
    """Compare fixed and bracket-fill Roth conversion scenarios for one detailed-holdings plan."""
    request = RothConversionInput(
        base_input=base_input,
        annual_conversion_amounts=annual_conversion_amounts or [0, 25_000, 50_000, 100_000],
        conversion_policies=conversion_policies
        or ["fill_standard_deduction", "fill_12_percent_bracket", "fill_22_percent_bracket"],
        conversion_start_age=conversion_start_age,
        conversion_end_age=conversion_end_age,
    )
    return get_engine().compare_roth_conversions(request).model_dump(mode="json")


def optimize_roth_conversions_tool(
    base_input: dict[str, Any],
    annual_conversion_amounts: list[float] | None = None,
    conversion_policies: list[str] | None = None,
    candidate_start_ages: list[int] | None = None,
    window_lengths: list[int] | None = None,
) -> dict[str, Any]:
    """Search bounded Roth conversion windows and sizing rules for one plan."""
    request = RothOptimizationInput(
        base_input=base_input,
        annual_conversion_amounts=annual_conversion_amounts or [0, 25_000, 50_000, 100_000],
        conversion_policies=conversion_policies
        or ["fill_standard_deduction", "fill_12_percent_bracket", "fill_22_percent_bracket"],
        candidate_start_ages=candidate_start_ages,
        window_lengths=window_lengths or [5, 10],
    )
    return get_engine().optimize_roth_conversions(request).model_dump(mode="json")


def optimize_roth_conversions_report_tool(
    base_input: dict[str, Any],
    annual_conversion_amounts: list[float] | None = None,
    conversion_policies: list[str] | None = None,
    candidate_start_ages: list[int] | None = None,
    window_lengths: list[int] | None = None,
) -> dict[str, Any]:
    """Search Roth conversion candidates and return an export-friendly report artifact."""
    request = RothOptimizationInput(
        base_input=base_input,
        annual_conversion_amounts=annual_conversion_amounts or [0, 25_000, 50_000, 100_000],
        conversion_policies=conversion_policies
        or ["fill_standard_deduction", "fill_12_percent_bracket", "fill_22_percent_bracket"],
        candidate_start_ages=candidate_start_ages,
        window_lengths=window_lengths or [5, 10],
    )
    result = get_engine().optimize_roth_conversions(request)
    return build_roth_optimization_report_artifact(result).model_dump(mode="json")


def compare_allocations_tool(
    base_input: dict[str, Any],
    allocations: list[float] | None = None,
) -> dict[str, Any]:
    """Compare alternative stock/bond mixes."""
    request = AllocationInput(base_input=base_input, allocations=allocations or [0.2, 0.4, 0.6, 0.8, 1.0])
    return get_engine().compare_allocations(request).model_dump(mode="json")


def compare_social_security_timing_tool(
    base_input: dict[str, Any],
    birth_year: int,
    pia_monthly: float,
    claiming_ages: list[int] | None = None,
) -> dict[str, Any]:
    """Compare Social Security claiming ages on one plan."""
    request = SSTimingInput(
        base_input=base_input,
        birth_year=birth_year,
        pia_monthly=pia_monthly,
        claiming_ages=claiming_ages or [62, 63, 64, 65, 66, 67, 68, 69, 70],
    )
    return get_engine().compare_ss_timing(request).model_dump(mode="json")


def calculate_household_tool(household: dict[str, Any]) -> dict[str, Any]:
    """Calculate taxes and benefits for one household."""
    request = HouseholdInput.model_validate(household)
    return get_engine().calculate_household(request).model_dump(mode="json")


def compare_life_event_tool(
    before: dict[str, Any],
    after: dict[str, Any],
    event_name: str = "Life Event",
) -> dict[str, Any]:
    """Compare taxes and benefits before and after one life event."""
    request = LifeEventComparisonInput(before=before, after=after, event_name=event_name)
    return get_engine().compare_life_event(request).model_dump(mode="json")


def analyze_compensation_tool(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Analyze employer-side packages and employee after-tax value."""
    request = CompensationAnalysisInput.model_validate(input_data)
    return [
        result.model_dump(mode="json")
        for result in get_engine().analyze_compensation(request)
    ]
