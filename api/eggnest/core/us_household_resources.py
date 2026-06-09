"""US household resource calculation engine.

This engine exposes annual household taxes, selected benefits, and net
resources through the same core envelope used by simulation engines.
"""

from __future__ import annotations

from typing import Any

from eggnest import __version__
from eggnest.citations import household_resource_citations
from eggnest.household import HouseholdCalculator
from eggnest.models import HouseholdInput, HouseholdResult

from .schemas import (
    SCENARIO_SCHEMA_VERSION,
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
    package_version,
)

ENGINE_ID = "us_household_resources"
ENGINE_COUNTRY = "USA"
ENGINE_VERSION = "0.1.0"
OUTPUT_KEY = "household_resources_result"


def build_us_household_resources_scenario(
    inputs: HouseholdInput | dict[str, Any],
    tags: dict[str, str] | None = None,
) -> EngineScenario:
    """Build a canonical core scenario from US household inputs."""
    parsed = (
        inputs
        if isinstance(inputs, HouseholdInput)
        else HouseholdInput.model_validate(inputs)
    )
    return EngineScenario(
        schema_version=SCENARIO_SCHEMA_VERSION,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        inputs=parsed.model_dump(),
        tags=tags or {},
    )


def run_us_household_resources(
    scenario_or_inputs: EngineScenario | HouseholdInput | dict[str, Any],
) -> EngineResult:
    """Run the US household resources engine and return a core envelope."""
    scenario, inputs = _normalize_scenario(scenario_or_inputs)
    result = HouseholdCalculator().calculate(inputs)
    return build_us_household_resources_result(scenario, inputs, result)


def build_us_household_resources_result(
    scenario: EngineScenario,
    inputs: HouseholdInput,
    result: HouseholdResult,
) -> EngineResult:
    """Wrap a household result in the stable core result envelope."""
    return EngineResult(
        scenario_schema_version=scenario.schema_version,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        assumptions=_assumptions(inputs),
        outputs={OUTPUT_KEY: result.model_dump()},
        citations=household_resource_citations(result),
        sources=_sources(),
        caveats=_caveats(),
        reproducibility=Reproducibility(
            engine_version=ENGINE_VERSION,
            model_version=__version__,
            parameter_year=inputs.year,
            tax_engine_versions={
                "policyengine-us": package_version("policyengine-us"),
                "policyengine-core": package_version("policyengine-core"),
            },
        ),
    )


def extract_us_household_resources_result(result: EngineResult) -> HouseholdResult:
    """Extract the legacy household result payload from a core result."""
    return HouseholdResult.model_validate(result.outputs[OUTPUT_KEY])


def _normalize_scenario(
    scenario_or_inputs: EngineScenario | HouseholdInput | dict[str, Any],
) -> tuple[EngineScenario, HouseholdInput]:
    if isinstance(scenario_or_inputs, EngineScenario):
        if scenario_or_inputs.engine != ENGINE_ID:
            raise ValueError(
                f"Unsupported US household engine: {scenario_or_inputs.engine}"
            )
        inputs = HouseholdInput.model_validate(scenario_or_inputs.inputs)
        return scenario_or_inputs, inputs

    scenario = build_us_household_resources_scenario(scenario_or_inputs)
    inputs = HouseholdInput.model_validate(scenario.inputs)
    return scenario, inputs


def _assumptions(inputs: HouseholdInput) -> dict[str, Any]:
    return {
        "currency": "USD",
        "state": inputs.state,
        "year": inputs.year,
        "filing_status": inputs.filing_status,
        "household_size": len(inputs.people),
        "policy_engine": "policyengine-us",
        "income_fields": [
            "employment_income",
            "self_employment_income",
            "social_security",
            "pension_income",
            "investment_income",
            "capital_gains",
        ],
        "benefit_outputs": [
            "child_tax_credit",
            "eitc",
            "snap",
            "child_care_credit",
        ],
        "tax_credit_accounting": (
            "Federal income tax is reported after non-refundable credits and before "
            "refundable credits; refundable credits are included in total benefits."
        ),
    }


def _sources() -> list[ModelSource]:
    return [
        ModelSource(
            name="PolicyEngine US",
            url="https://github.com/PolicyEngine/policyengine-us",
            version=package_version("policyengine-us"),
            notes="Computes federal taxes, state taxes, tax credits, and selected benefits.",
        ),
        ModelSource(
            name="PolicyEngine Core",
            url="https://github.com/PolicyEngine/policyengine-core",
            version=package_version("policyengine-core"),
            notes="Microsimulation framework used by PolicyEngine US.",
        ),
    ]


def _caveats() -> list[str]:
    return [
        "Educational calculator output only; not financial, tax, legal, or benefits application advice.",
        "This engine reports annual modeled resources and selected benefits; it is not a full benefits eligibility screener.",
        "Program details, take-up, documentation requirements, and local administration are not fully modeled.",
    ]
