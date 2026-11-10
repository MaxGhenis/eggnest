"""Dispatch core scenarios to calculation engines."""

from __future__ import annotations

from .schemas import EngineResult, EngineScenario
from .uk_drawdown_year import run_uk_drawdown_year_scenario
from .uk_retirement import run_uk_retirement
from .us_drawdown_year import run_us_drawdown_year_scenario
from .us_household_resources import run_us_household_resources
from .us_retirement import run_us_retirement


def run_core_scenario(scenario: EngineScenario) -> EngineResult:
    """Run a core scenario through the requested engine."""
    if scenario.engine == "us_retirement":
        return run_us_retirement(scenario)
    if scenario.engine == "uk_retirement":
        return run_uk_retirement(scenario)
    if scenario.engine == "us_household_resources":
        return run_us_household_resources(scenario)
    if scenario.engine == "uk_drawdown_year":
        return run_uk_drawdown_year_scenario(scenario)
    if scenario.engine == "us_drawdown_year":
        return run_us_drawdown_year_scenario(scenario)
    raise ValueError(f"Unsupported engine: {scenario.engine}")
