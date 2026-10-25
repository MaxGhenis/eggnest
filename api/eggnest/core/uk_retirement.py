"""UK retirement calculation engine.

This module is the first strangler boundary: it exposes a stable core envelope
while delegating the current numerical implementation to ``simulation_uk``.
"""

from __future__ import annotations

from typing import Any

from eggnest import __version__
from eggnest.models_uk import UKSimulationInput, UKSimulationResult
from eggnest.simulation_uk import (
    LSA_CAP,
    MPA,
    TFC_FRACTION,
    UNMET_TOLERANCE,
    run_uk_simulation,
)
from eggnest.tax_uk import (
    AXIOM_UK_TAX_ENGINE,
    LATEST_PARAMETER_YEAR,
    POLICYENGINE_UK_TAX_ENGINE,
)

from .schemas import (
    SCENARIO_SCHEMA_VERSION,
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
    package_version,
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
    citations = []
    if result.pension_credit is not None:
        from eggnest.citations import Citation

        citations = [
            Citation(id=ref.id, url=ref.url) for ref in result.pension_credit.citations
        ]
    tax_engine = result.metadata.get("tax_engine", POLICYENGINE_UK_TAX_ENGINE)
    axiom_tax = tax_engine == AXIOM_UK_TAX_ENGINE
    # The Axiom engine runs the tax, the Pension Credit screen, or both. A
    # screen that ends before the qualifying age calls no engine.
    axiom_screen = (
        result.pension_credit is not None and result.pension_credit.status == "screened"
    )
    axiom_versions = {}
    if axiom_tax or axiom_screen:
        from eggnest import axiom_uk

        axiom_versions = axiom_uk.versions()
    tax_engine_versions = (
        dict(axiom_versions)
        if axiom_tax
        else {
            POLICYENGINE_UK_TAX_ENGINE: package_version("policyengine-uk-compiled"),
            **axiom_versions,
        }
    )
    return EngineResult(
        scenario_schema_version=scenario.schema_version,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        assumptions=_assumptions(inputs, axiom_tax=axiom_tax),
        outputs={OUTPUT_KEY: result.model_dump()},
        citations=citations,
        sources=_sources(
            axiom_tax=axiom_tax,
            axiom_screen=axiom_screen,
            axiom_versions=axiom_versions,
        ),
        caveats=_caveats(inputs, axiom_tax=axiom_tax),
        reproducibility=Reproducibility(
            engine_version=ENGINE_VERSION,
            model_version=__version__,
            random_seed=inputs.random_seed,
            parameter_year=None if axiom_tax else LATEST_PARAMETER_YEAR,
            tax_engine_versions=tax_engine_versions,
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


def _assumptions(inputs: UKSimulationInput, *, axiom_tax: bool) -> dict[str, Any]:
    return {
        "currency": "GBP",
        "spending_mode": inputs.spending_mode,
        "return_source": inputs.return_source,
        "equity_weight": inputs.equity_weight,
        "earnings_model": inputs.earnings_model,
        "include_mortality": inputs.include_mortality,
        "tax_engine": AXIOM_UK_TAX_ENGINE if axiom_tax else POLICYENGINE_UK_TAX_ENGINE,
        "tax_parameter_year_policy": (
            "Each tax year uses the rulespec-uk parameter versions in effect "
            "at its start (the latest encoded version for later years), with "
            "the cited runtime values in eggnest/data/axiom_uk_parameters.yaml."
            if axiom_tax
            else f"Years after {LATEST_PARAMETER_YEAR} use the latest available "
            "PolicyEngine UK compiled parameters."
        ),
        "account_rules": {
            "sipp_minimum_pension_age": MPA,
            "ufpls_tax_free_fraction": TFC_FRACTION,
            "lump_sum_allowance_cap": LSA_CAP,
        },
        "success_definition": (
            "A path succeeds if no simulated year it is alive has more than "
            f"£{UNMET_TOLERANCE:.0f} of the spending target unmet."
        ),
        "returns": (
            "ISA and SIPP balances earn the total return; GIA dividends are "
            "paid out as taxable income and reinvested when not spent."
        ),
    }


def _sources(
    *, axiom_tax: bool, axiom_screen: bool, axiom_versions: dict[str, str]
) -> list[ModelSource]:
    tax_notes = (
        "Computes UK income tax (including dividend tax) and employee "
        "National Insurance for each person."
    )
    sources = []
    if not axiom_tax:
        sources.append(
            ModelSource(
                name="PolicyEngine UK compiled",
                url="https://github.com/PolicyEngine/policyengine-uk-compiled",
                version=package_version("policyengine-uk-compiled"),
                notes=tax_notes,
            )
        )
    if axiom_versions:
        uses = [tax_notes] if axiom_tax else []
        if axiom_screen:
            uses.append("Screens Pension Credit guarantee credit (pension_credit).")
        sources += [
            ModelSource(
                name="Axiom rules engine",
                url="https://github.com/TheAxiomFoundation/axiom-rules-engine",
                version=axiom_versions.get("axiom-rules-engine"),
                notes=" ".join(uses),
            ),
            ModelSource(
                name="rulespec-uk",
                url="https://github.com/TheAxiomFoundation/rulespec-uk",
                version=axiom_versions.get("rulespec-uk"),
                notes="Statute encodings the Axiom rules engine executes.",
            ),
        ]
    return sources + [
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


def _caveats(inputs: UKSimulationInput, *, axiom_tax: bool = False) -> list[str]:
    caveats = [
        "Educational calculator output only; not financial, tax, or legal advice.",
        "Single-person UK simulator; couples, annuities, and means-tested benefits are not yet modeled.",
        (
            "Future tax years beyond the encoded rulespec-uk parameter versions use the latest encoded version."
            if axiom_tax
            else "Future tax years beyond available PolicyEngine UK parameters use the latest available parameter year."
        ),
        "Net income is income less income tax and employee National Insurance; benefits such as Pension Credit and Universal Credit are not added.",
        "Neither the State Pension nor earnings is uprated with inflation: the State Pension stays at its input amount and earnings follow the chosen earnings model.",
        "GIA sales are modeled without Capital Gains Tax, and pension contributions without tax relief.",
        "State Pension age follows Pensions Act 1995 Sch 4 for a birth date one current_age before the run date; employee National Insurance stops on earnings after it.",
        "SIPP money cannot be drawn before the minimum pension age; spending it cannot cover counts as unmet (sipp_locked_shortfall_rate).",
    ]
    caveats.append(
        "pension_credit, when present, is a guarantee credit screen (State Pension Credit Act 2002 s.2; SI 2002/1792 regs 6 and 15(6)) of up to 500 simulated paths, not a benefits decision. It counts the State Pension from the qualifying age even when its claim is deferred (reg 18(1)) and compares every simulated year with today's minimum guarantee, using that year's nominal income and capital. It omits notional income from undrawn pension pots (reg 18), savings credit and housing costs, and is never added to spendable income."
    )
    if inputs.include_mortality:
        caveats.append(
            "success_rate is mortality-adjusted: a path succeeds if spending is met in every simulated year the person is alive."
        )
    if inputs.return_source.startswith("historical"):
        caveats.append(
            "Historical return paths use available UK historical market data and do not forecast structural regime changes."
        )
    return caveats
