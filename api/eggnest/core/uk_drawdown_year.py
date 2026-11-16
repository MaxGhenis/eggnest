"""Core envelope for the one-year UK drawdown calculator."""

from __future__ import annotations

from datetime import date
from typing import Any

from eggnest import __version__, axiom_uk
from eggnest.citations import Citation
from eggnest.drawdown_uk import run_uk_drawdown_year
from eggnest.models_uk_drawdown import (
    UKDrawdownYearInput,
    UKDrawdownYearResult,
    minimum_pension_age_date,
    pot_locked_all_year,
)
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


def _day(value: date) -> str:
    return f"{value.day} {value:%B %Y}"


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
                "credit from rulespec-uk encodings. Eggnest applies by hand the "
                "rules those encodings don't yet cover: which money counts as "
                "income or capital for Pension Credit, notional income from an "
                "undrawn pot, the £5 earnings disregard, tax off counted income, "
                "the State Pension paid from State Pension age, tax-free cash "
                "and the minimum pension age."
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
        _local_help_caveat(inputs),
        "We don’t cover Scottish taxpayers, who pay the income tax rates the Scottish Parliament sets.",
        "We count Pension Credit for every eligible week of the tax year; a claim that starts part way through pays less.",
        "We assume you spend the money you draw evenly through the year. DWP can treat someone as still holding money they spent or gave away to get or increase Pension Credit (SI 2002/1792 regs 18(6) and 21).",
        "We value an undrawn pot from the Government Actuary’s table, and DWP decision makers also weigh evidence from the pension provider (DMG 85470-85471). DWP decides whether withdrawals count as regular or one-off (DMG 85456-85457).",
        "We count all of a regular withdrawal as income, its tax-free part included, reading DMG 85456 and 85476 that way. DMG 85472 treats a lump sum of up to 25% taken when income starts as capital; if DWP treats your tax-free part that way, Pension Credit here may be too low.",
        "We take the tax payable on counted income off that income (SI 2002/1792 reg 17(10)) and take no tax off income DWP only assumes a pot produces.",
    ]
    caveats += _state_pension_caveats(inputs)
    if inputs.draw_source == "sipp":
        turns_55 = minimum_pension_age_date(inputs.birth_date)
        if pot_locked_all_year(inputs):
            caveats.append(
                f"You turn 55 on {_day(turns_55)}, after this tax year ends, and pension rules let a pot pay you a pension or lump sum only from then (Finance Act 2004 s.165 pension rule 1, Sch 29 paras 1(1)(d) and 4A(1)(c), and s.279), so we show no draw from your pot this year."
            )
        elif turns_55 > date(inputs.tax_year, 4, 6):
            caveats.append(
                f"You turn 55 on {_day(turns_55)}, and pension rules let a pot pay you only from then (Finance Act 2004 s.165 pension rule 1 and s.279), so take this draw on or after that day."
            )
    if inputs.draw_source == "gia" or inputs.gia_balance > 0:
        caveats.append(
            "We leave out Capital Gains Tax on selling investments outside ISAs."
        )
        caveats.append(
            "We count investments outside an ISA at full value. DWP takes 10% off shares for the cost of selling them (SI 2002/1792 reg 19; DMG 84763), though not off unit trusts (DMG 84772), so if you hold shares, Pension Credit here may be too low."
        )
    # Women born before 6 April 1953 reached State Pension age before 6 April
    # 2016; men born before 6 April 1951 did. The page doesn't ask sex, so the
    # caveat shows for anyone born before the later date and names both.
    if state_pension_age_date(inputs.birth_date, "female") < SAVINGS_CREDIT_CUTOFF:
        caveats.append(
            "Women born before 6 April 1953 and men born before 6 April 1951 reached State Pension age before 6 April 2016 and can qualify for Savings Credit (State Pension Credit Act 2002 s.3), so for them Pension Credit here may be too low."
        )
    if inputs.region == "Northern Ireland":
        caveats.append(
            "We apply Great Britain’s Pension Credit regulations; Northern Ireland has its own (SR 2003 No. 28)."
        )
    return caveats


def _local_help_caveat(inputs: UKDrawdownYearInput) -> str:
    """Help with rent and council tax or rates, which the result leaves out."""
    if inputs.region == "Northern Ireland":
        return "We leave out Housing Benefit and help with rates, which Northern Ireland runs under its own rules. Both are means-tested, so losing Guarantee Credit can cost more than this result shows."
    if inputs.region == "Wales":
        return "We leave out Housing Benefit and Council Tax Reduction. People on Guarantee Credit pass the income and capital tests for Housing Benefit automatically (SI 2006/214 reg 26), and Wales sets its own Council Tax Reduction rules, so losing Guarantee Credit can cost more than this result shows."
    return "We leave out Housing Benefit and Council Tax Reduction. People on Guarantee Credit pass the income and capital tests for both automatically (SI 2006/214 reg 26; SI 2012/2885 Sch 1 para 13), so losing Guarantee Credit can cost more than this result shows."


def _state_pension_caveats(inputs: UKDrawdownYearInput) -> list[str]:
    """When the State Pension starts, and what deferring it changes."""
    if inputs.state_pension <= 0:
        return []
    # Births from 6 December 1953 share one State Pension age; everyone born
    # earlier reached both before this tax year.
    reached = state_pension_age_date(inputs.birth_date, "female")
    starts = date(inputs.tax_year, 4, 6)
    ends = date(inputs.tax_year + 1, 4, 5)
    if reached > ends:
        return [
            f"You reach State Pension age on {_day(reached)}, after this tax year, so we count no State Pension."
        ]
    caveats = []
    if inputs.state_pension_deferred:
        deferred = "You haven't claimed your State Pension, so we leave it out of tax and money to spend. Pension Credit still counts it from State Pension age as if you had claimed it (SI 2002/1792 reg 18(1))."
        # Reg 18(1B) reaches only the State Pension of people who reached
        # State Pension age before 6 April 2016 (SPCA 2002 s.16(1)(a)-(c)).
        # The page doesn't ask sex, so the women's later date decides.
        if reached < SAVINGS_CREDIT_CUTOFF:
            deferred += " For an older State Pension (State Pension age before 6 April 2016) deferred 12 months or more, DWP counts the weekly pension you would get if you chose the lump sum for deferring, which leaves out the extra pension deferring earns (reg 18(1B); DMG 85445-85446), so enter that rate."
        caveats.append(deferred)
    elif reached > starts:
        caveats.append(
            f"You reach State Pension age on {_day(reached)}. We count your State Pension from that day: a share of the yearly rate for tax and money to spend, and the weekly rate in each week Pension Credit covers."
        )
    return caveats
