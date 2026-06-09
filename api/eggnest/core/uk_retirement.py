"""UK retirement calculation engine.

This module is the first strangler boundary: it exposes a stable core envelope
while delegating the current numerical implementation to ``simulation_uk``.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from eggnest import __version__
from eggnest.models_uk import UKSimulationInput, UKSimulationResult
from eggnest.simulation_uk import run_uk_simulation
from eggnest.tax_uk import LATEST_PARAMETER_YEAR

from .schemas import (
    SCENARIO_SCHEMA_VERSION,
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
)

ENGINE_ID = "uk_retirement"
ENGINE_COUNTRY = "GBR"
ENGINE_VERSION = "0.1.0"
OUTPUT_KEY = "uk_simulation_result"


def build_uk_retirement_scenario(
    inputs: UKSimulationInput | dict[str, Any],
    tags: dict[str, str] | None = None,
) -> EngineScenario:
    """Build a canonical core scenario from UK simulator inputs."""
    parsed = (
        inputs
        if isinstance(inputs, UKSimulationInput)
        else UKSimulationInput.model_validate(inputs)
    )
    return EngineScenario(
        schema_version=SCENARIO_SCHEMA_VERSION,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        inputs=parsed.model_dump(),
        tags=tags or {},
    )


def run_uk_retirement(
    scenario_or_inputs: EngineScenario | UKSimulationInput | dict[str, Any],
) -> EngineResult:
    """Run the UK retirement engine and return a canonical result envelope."""
    scenario, inputs = _normalize_scenario(scenario_or_inputs)
    result = run_uk_simulation(inputs)
    return build_uk_retirement_result(scenario, inputs, result)


def build_uk_retirement_result(
    scenario: EngineScenario,
    inputs: UKSimulationInput,
    result: UKSimulationResult,
) -> EngineResult:
    """Wrap a UK simulator result in the stable core result envelope."""
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
            parameter_year=LATEST_PARAMETER_YEAR,
            tax_engine_versions={
                "policyengine-uk-compiled": _package_version("policyengine-uk-compiled")
            },
        ),
    )


def extract_uk_simulation_result(result: EngineResult) -> UKSimulationResult:
    """Extract the legacy UK result payload from a core engine result."""
    return UKSimulationResult.model_validate(result.outputs[OUTPUT_KEY])


def _normalize_scenario(
    scenario_or_inputs: EngineScenario | UKSimulationInput | dict[str, Any],
) -> tuple[EngineScenario, UKSimulationInput]:
    if isinstance(scenario_or_inputs, EngineScenario):
        if scenario_or_inputs.engine != ENGINE_ID:
            raise ValueError(f"Unsupported UK engine: {scenario_or_inputs.engine}")
        inputs = UKSimulationInput.model_validate(scenario_or_inputs.inputs)
        return scenario_or_inputs, inputs

    scenario = build_uk_retirement_scenario(scenario_or_inputs)
    inputs = UKSimulationInput.model_validate(scenario.inputs)
    return scenario, inputs


def _assumptions(inputs: UKSimulationInput) -> dict[str, Any]:
    return {
        "currency": "GBP",
        "spending_mode": inputs.spending_mode,
        "return_source": inputs.return_source,
        "equity_weight": inputs.equity_weight,
        "earnings_model": inputs.earnings_model,
        "include_mortality": inputs.include_mortality,
        "tax_parameter_year_policy": (
            f"Years after {LATEST_PARAMETER_YEAR} use the latest available "
            "PolicyEngine UK compiled parameters."
        ),
        "account_rules": {
            "sipp_minimum_pension_age": 55,
            "ufpls_tax_free_fraction": 0.25,
            "lump_sum_allowance_cap": 268_275.0,
        },
    }


def _sources() -> list[ModelSource]:
    return [
        ModelSource(
            name="PolicyEngine UK compiled",
            url="https://github.com/PolicyEngine/policyengine-uk-compiled",
            version=_package_version("policyengine-uk-compiled"),
            notes="Computes UK income tax, National Insurance, and dividend tax.",
        ),
        ModelSource(
            name="JST Macrohistory Database",
            url="https://www.macrohistory.net/database/",
            notes=(
                "Historical UK equity, gilt, and CPI data used by the "
                "historical return samplers."
            ),
        ),
        ModelSource(
            name="UK pension tax wrapper rules",
            notes=(
                "Models ISA/GIA/SIPP account treatment, UFPLS 25% tax-free "
                "cash, Minimum Pension Age, and Lump Sum Allowance."
            ),
        ),
    ]


def _caveats(inputs: UKSimulationInput) -> list[str]:
    caveats = [
        "Educational calculator output only; not financial, tax, or legal advice.",
        "Single-person UK simulator; couples, annuities, and means-tested benefits are not yet modeled.",
        "Future tax years beyond available PolicyEngine UK parameters use the latest available parameter year.",
    ]
    if inputs.include_mortality:
        caveats.append(
            "success_rate is mortality-adjusted: paths that avoid depletion before death or horizon count as successful."
        )
    if inputs.return_source.startswith("historical"):
        caveats.append(
            "Historical return paths use available UK historical market data and do not forecast structural regime changes."
        )
    return caveats


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"
