"""Core envelope for the one-year UK drawdown calculator."""

from __future__ import annotations

from datetime import date
from typing import Any

from eggnest import __version__, axiom_uk
from eggnest.citations import Citation
from eggnest.drawdown_uk import run_uk_drawdown_year
from eggnest.models_uk_drawdown import UKDrawdownYearInput, UKDrawdownYearResult
from eggnest.state_pension_age import state_pension_age_date
from eggnest.tax_uk import AXIOM_UK_TAX_ENGINE

from .schemas import (
    SCENARIO_SCHEMA_VERSION,
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
)

ENGINE_ID = "uk_drawdown_year"
ENGINE_COUNTRY = "GBR"
ENGINE_VERSION = "0.1.0"
OUTPUT_KEY = "uk_drawdown_year_result"
SAVINGS_CREDIT_CUTOFF = date(2016, 4, 6)  # State Pension Credit Act 2002 s.3(1)


def build_uk_drawdown_year_scenario(
    inputs: UKDrawdownYearInput | dict[str, Any],
    tags: dict[str, str] | None = None,
) -> EngineScenario:
    """Build a canonical core scenario from drawdown calculator inputs."""
    parsed = (
        inputs
        if isinstance(inputs, UKDrawdownYearInput)
        else UKDrawdownYearInput.model_validate(inputs)
    )
    return EngineScenario(
        schema_version=SCENARIO_SCHEMA_VERSION,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        inputs=parsed.model_dump(mode="json"),
        tags=tags or {},
    )


def run_uk_drawdown_year_scenario(
    scenario_or_inputs: EngineScenario | UKDrawdownYearInput | dict[str, Any],
) -> EngineResult:
    """Run the calculator and return the canonical result envelope."""
    scenario, inputs = _normalize_scenario(scenario_or_inputs)
    return build_uk_drawdown_year_result(scenario, inputs, run_uk_drawdown_year(inputs))


def build_uk_drawdown_year_result(
    scenario: EngineScenario,
    inputs: UKDrawdownYearInput,
    result: UKDrawdownYearResult,
) -> EngineResult:
    """Wrap a calculator result in the stable core result envelope."""
    versions = axiom_uk.versions()
    return EngineResult(
        scenario_schema_version=scenario.schema_version,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        assumptions=_assumptions(inputs, result),
        outputs={OUTPUT_KEY: result.model_dump(mode="json")},
        citations=_citations(result),
        sources=_sources(versions),
        caveats=caveats_for(inputs),
        reproducibility=Reproducibility(
            engine_version=ENGINE_VERSION,
            model_version=__version__,
            parameter_year=inputs.tax_year,
            tax_engine_versions=versions,
        ),
    )


def extract_uk_drawdown_year_result(result: EngineResult) -> UKDrawdownYearResult:
    """Extract the calculator result from a core engine result."""
    return UKDrawdownYearResult.model_validate(result.outputs[OUTPUT_KEY])


def _normalize_scenario(
    scenario_or_inputs: EngineScenario | UKDrawdownYearInput | dict[str, Any],
) -> tuple[EngineScenario, UKDrawdownYearInput]:
    if isinstance(scenario_or_inputs, EngineScenario):
        if scenario_or_inputs.engine != ENGINE_ID:
            raise ValueError(
                f"Unsupported UK drawdown engine: {scenario_or_inputs.engine}"
            )
        inputs = UKDrawdownYearInput.model_validate(scenario_or_inputs.inputs)
        return scenario_or_inputs, inputs
    scenario = build_uk_drawdown_year_scenario(scenario_or_inputs)
    return scenario, UKDrawdownYearInput.model_validate(scenario.inputs)


def _citations(result: UKDrawdownYearResult) -> list[Citation]:
    seen: dict[tuple[str, str], Citation] = {}
    for figure in (result.income_tax, result.employee_ni, result.pension_credit):
        for ref in figure.citations:
            seen.setdefault((ref.id, ref.url), Citation(id=ref.id, url=ref.url))
    return list(seen.values())


def _assumptions(
    inputs: UKDrawdownYearInput, result: UKDrawdownYearResult
) -> dict[str, Any]:
    return {
        "currency": "GBP",
        "tax_year": result.tax_year_label,
        "tax_engine": AXIOM_UK_TAX_ENGINE,
        "pension_credit_engine": AXIOM_UK_TAX_ENGINE,
        "household": "one person living alone",
        "weeks_assessed": 52,
        "money_drawn": "spent evenly through the tax year",
        "regular_pot_withdrawals": "income for Pension Credit (DMG 85456, 85476)",
        "one_off_pot_withdrawals": "capital for Pension Credit (DMG 85457)",
        "undrawn_pot": (
            "counted at the annuity rate the fund could buy (SI 2002/1792 reg "
            "18(2)-(3); DMG 85460), less regular withdrawals"
        ),
        "annuity_income_per_1000": (
            result.pension_credit_working.annuity_income_per_1000
        ),
        "annuity_rate_source": (
            "the caller's provider figure"
            if inputs.annuity_income_per_1000 is not None
            else "GAD drawdown pension tables, Table 1, effective 1 September 2025"
        ),
        "gilt_yield_percent_used": result.assumptions.gilt_yield_percent_used,
        "capital": (
            "ISA, GIA and cash balances at full value; the 10% deduction for "
            "sale expenses (reg 19) is not applied"
        ),
        "tax_free_fraction": result.assumptions.tax_free_fraction_applied,
    }


def _sources(versions: dict[str, str]) -> list[ModelSource]:
    return [
        ModelSource(
            name="Axiom rules engine",
            url="https://github.com/TheAxiomFoundation/axiom-rules-engine",
            version=versions.get("axiom-rules-engine"),
            notes=(
                "Computes income tax, employee National Insurance and guarantee "
                "credit from rulespec-uk encodings."
            ),
        ),
        ModelSource(
            name="rulespec-uk",
            url="https://github.com/TheAxiomFoundation/rulespec-uk",
            version=versions.get("rulespec-uk"),
            notes="Statute encodings the Axiom rules engine executes.",
        ),
        ModelSource(
            name="GAD drawdown pension tables",
            url="https://www.gov.uk/government/publications/drawdown-pension-tables",
            notes=(
                "Values an undrawn pot at the annuity income it could buy, as "
                "DWP guidance (DMG 85470) describes."
            ),
        ),
    ]


def caveats_for(inputs: UKDrawdownYearInput) -> list[str]:
    """What this result leaves out, specific to these inputs where it can be."""
    caveats = [
        "We give educational estimates, not financial, tax or legal advice or a benefits decision.",
        "We cover one person living alone, and leave out couples, additional amounts for severe disability or caring, and Savings Credit.",
        "We leave out Housing Benefit and Council Tax Reduction. People on Guarantee Credit pass the income and capital tests for both automatically (SI 2006/214 reg 26; SI 2012/2885 Sch 1 para 13), so losing it can cost more than this result shows.",
        "We don’t cover Scottish taxpayers, who pay the income tax rates the Scottish Parliament sets.",
        "We count Pension Credit for every eligible week of the tax year; a claim that starts part way through pays less.",
        "We assume you spend the money you draw evenly through the year. DWP can treat someone as still holding money they spent or gave away to get or increase Pension Credit (SI 2002/1792 regs 18(6) and 21).",
        "We value an undrawn pot from the Government Actuary’s table, and DWP decision makers also weigh evidence from the pension provider (DMG 85470-85471). DWP decides whether withdrawals count as regular or one-off (DMG 85456-85457).",
        "We count all of a regular withdrawal as income, tax-free part included (DMG 85456, 85476).",
        "We take the tax payable on counted income off that income (SI 2002/1792 reg 17(10)) and take no tax off income DWP only assumes a pot produces.",
    ]
    if inputs.draw_source == "gia" or inputs.gia_balance > 0:
        caveats.append(
            "We leave out Capital Gains Tax on selling investments outside ISAs."
        )
    if state_pension_age_date(inputs.birth_date, "female") < SAVINGS_CREDIT_CUTOFF:
        caveats.append(
            "Someone who reached State Pension age before 6 April 2016 can qualify for Savings Credit (State Pension Credit Act 2002 s.3), so Pension Credit here may be too low."
        )
    if inputs.region == "Northern Ireland":
        caveats.append(
            "We apply Great Britain’s Pension Credit regulations; Northern Ireland has its own (SR 2003 No. 28)."
        )
    return caveats
