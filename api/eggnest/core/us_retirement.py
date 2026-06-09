"""US retirement calculation engine.

This module exposes the stable core scenario/result envelope while delegating
the current numerical implementation to ``simulation.MonteCarloSimulator``.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from eggnest import __version__
from eggnest.models import SimulationInput, SimulationResult
from eggnest.simulation import START_YEAR, MonteCarloSimulator

from .schemas import (
    SCENARIO_SCHEMA_VERSION,
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
)

ENGINE_ID = "us_retirement"
ENGINE_COUNTRY = "USA"
ENGINE_VERSION = "0.1.0"
OUTPUT_KEY = "us_simulation_result"


def build_us_retirement_scenario(
    inputs: SimulationInput | dict[str, Any],
    tags: dict[str, str] | None = None,
) -> EngineScenario:
    """Build a canonical core scenario from US simulator inputs."""
    parsed = (
        inputs if isinstance(inputs, SimulationInput) else SimulationInput(**inputs)
    )
    return EngineScenario(
        schema_version=SCENARIO_SCHEMA_VERSION,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        inputs=parsed.model_dump(),
        tags=tags or {},
    )


def run_us_retirement(
    scenario_or_inputs: EngineScenario | SimulationInput | dict[str, Any],
) -> EngineResult:
    """Run the US retirement engine and return a canonical result envelope."""
    scenario, inputs = _normalize_scenario(scenario_or_inputs)
    result = MonteCarloSimulator(inputs).run()
    return build_us_retirement_result(scenario, inputs, result)


def build_us_retirement_result(
    scenario: EngineScenario,
    inputs: SimulationInput,
    result: SimulationResult,
) -> EngineResult:
    """Wrap a US simulator result in the stable core result envelope."""
    return EngineResult(
        scenario_schema_version=scenario.schema_version,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        assumptions=_assumptions(inputs),
        outputs={OUTPUT_KEY: result.model_dump()},
        sources=_sources(),
        caveats=_caveats(inputs),
        reproducibility=Reproducibility(
            engine_version=ENGINE_VERSION,
            model_version=__version__,
            random_seed=inputs.random_seed,
            parameter_year=START_YEAR,
            tax_engine_versions={
                "policyengine-us": _package_version("policyengine-us"),
                "policyengine-core": _package_version("policyengine-core"),
            },
        ),
    )


def extract_us_simulation_result(result: EngineResult) -> SimulationResult:
    """Extract the legacy US result payload from a core engine result."""
    return SimulationResult.model_validate(result.outputs[OUTPUT_KEY])


def _normalize_scenario(
    scenario_or_inputs: EngineScenario | SimulationInput | dict[str, Any],
) -> tuple[EngineScenario, SimulationInput]:
    if isinstance(scenario_or_inputs, EngineScenario):
        if scenario_or_inputs.engine != ENGINE_ID:
            raise ValueError(f"Unsupported US engine: {scenario_or_inputs.engine}")
        inputs = SimulationInput.model_validate(scenario_or_inputs.inputs)
        return scenario_or_inputs, inputs

    scenario = build_us_retirement_scenario(scenario_or_inputs)
    inputs = SimulationInput.model_validate(scenario.inputs)
    return scenario, inputs


def _assumptions(inputs: SimulationInput) -> dict[str, Any]:
    assumptions: dict[str, Any] = {
        "currency": "USD",
        "simulation_start_year": START_YEAR,
        "state": inputs.state,
        "filing_status": inputs.filing_status,
        "return_model": inputs.return_model,
        "stock_allocation": inputs.stock_allocation,
        "stock_index": inputs.stock_index,
        "bond_index": inputs.bond_index,
        "dividend_yield": inputs.dividend_yield,
        "include_mortality": inputs.include_mortality,
        "holdings_based": bool(inputs.holdings),
        "withdrawal_strategy": inputs.withdrawal_strategy,
        "tax_year_policy": (
            "Each simulated year is passed to PolicyEngine-US as a calendar year; "
            "availability and extrapolation are governed by the installed "
            "PolicyEngine-US package."
        ),
        "account_rules": {
            "traditional_accounts": "Withdrawals and RMDs are modeled as ordinary income.",
            "roth_accounts": "Withdrawals and dividends are modeled as tax-free in the portfolio simulator.",
            "taxable_accounts": "Realized taxable-account withdrawals are modeled as capital gains.",
        },
    }
    if inputs.return_model == "normal":
        assumptions["normal_return_model"] = {
            "expected_return": inputs.expected_return,
            "return_volatility": inputs.return_volatility,
        }
    return assumptions


def _sources() -> list[ModelSource]:
    return [
        ModelSource(
            name="PolicyEngine US",
            url="https://github.com/PolicyEngine/policyengine-us",
            version=_package_version("policyengine-us"),
            notes="Computes federal and state income tax liabilities.",
        ),
        ModelSource(
            name="PolicyEngine Core",
            url="https://github.com/PolicyEngine/policyengine-core",
            version=_package_version("policyengine-core"),
            notes="Microsimulation framework used by PolicyEngine US.",
        ),
        ModelSource(
            name="SSA Period Life Table",
            url="https://www.ssa.gov/oact/STATS/table4c6.html",
            notes="Mortality rates used for single and joint alive masks.",
        ),
        ModelSource(
            name="US market return datasets",
            notes=(
                "Historical S&P 500, US Treasury, VT, and BND price/dividend "
                "return series embedded in eggnest.returns."
            ),
        ),
    ]


def _caveats(inputs: SimulationInput) -> list[str]:
    caveats = [
        "Educational calculator output only; not financial, tax, or legal advice.",
        "Federal and state income taxes are modeled, but Medicare premiums, IRMAA, SNAP, SSI, and other benefits are not yet included in the US retirement simulator.",
        "Future tax years are limited by the installed PolicyEngine-US package behavior.",
    ]
    if inputs.include_mortality:
        caveats.append(
            "success_rate is mortality-adjusted: paths that avoid depletion before death or horizon count as successful."
        )
    if not inputs.holdings:
        caveats.append(
            "Legacy single-portfolio mode treats withdrawals as taxable capital gains; holdings mode is required for account-specific traditional, Roth, and taxable treatment."
        )
    return caveats


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"
