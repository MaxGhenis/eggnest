"""Core envelope for the one-year US drawdown calculator."""

from __future__ import annotations

from importlib.metadata import version as package_version
from typing import Any

from eggnest import __version__
from eggnest.drawdown_us import citations, run_us_drawdown_year
from eggnest.models_us_drawdown import (
    MEDICARE_PREMIUM_LAG_YEARS,
    USDrawdownYearInput,
    USDrawdownYearResult,
)

from .schemas import (
    SCENARIO_SCHEMA_VERSION,
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
)

ENGINE_ID = "us_drawdown_year"
ENGINE_COUNTRY = "USA"
ENGINE_VERSION = "0.1.0"
OUTPUT_KEY = "us_drawdown_year_result"
# The Joint and Last Survivor Table replaces the Uniform Lifetime Table when
# the sole beneficiary is a spouse more than 10 years younger
# (26 CFR 1.401(a)(9)-9; IRS Publication 590-B).
_JOINT_TABLE_AGE_GAP = 10


def build_us_drawdown_year_scenario(
    inputs: USDrawdownYearInput | dict[str, Any],
    tags: dict[str, str] | None = None,
) -> EngineScenario:
    """Build a canonical core scenario from drawdown calculator inputs."""
    parsed = (
        inputs
        if isinstance(inputs, USDrawdownYearInput)
        else USDrawdownYearInput.model_validate(inputs)
    )
    return EngineScenario(
        schema_version=SCENARIO_SCHEMA_VERSION,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        inputs=parsed.model_dump(mode="json"),
        tags=tags or {},
    )


def run_us_drawdown_year_scenario(
    scenario_or_inputs: EngineScenario | USDrawdownYearInput | dict[str, Any],
) -> EngineResult:
    """Run the calculator and return the canonical result envelope."""
    scenario, inputs = _normalize_scenario(scenario_or_inputs)
    return build_us_drawdown_year_result(scenario, inputs, run_us_drawdown_year(inputs))


def build_us_drawdown_year_result(
    scenario: EngineScenario,
    inputs: USDrawdownYearInput,
    result: USDrawdownYearResult,
) -> EngineResult:
    """Wrap a calculator result in the stable core result envelope."""
    versions = {
        "policyengine-us": package_version("policyengine-us"),
        "policyengine-core": package_version("policyengine-core"),
    }
    return EngineResult(
        scenario_schema_version=scenario.schema_version,
        engine=ENGINE_ID,
        country=ENGINE_COUNTRY,
        assumptions=_assumptions(inputs, result),
        outputs={OUTPUT_KEY: result.model_dump(mode="json")},
        citations=citations(result),
        sources=_sources(versions),
        caveats=caveats_for(inputs, result),
        reproducibility=Reproducibility(
            engine_version=ENGINE_VERSION,
            model_version=__version__,
            parameter_year=inputs.tax_year,
            tax_engine_versions=versions,
        ),
    )


def extract_us_drawdown_year_result(result: EngineResult) -> USDrawdownYearResult:
    """Extract the calculator result from a core engine result."""
    return USDrawdownYearResult.model_validate(result.outputs[OUTPUT_KEY])


def _normalize_scenario(
    scenario_or_inputs: EngineScenario | USDrawdownYearInput | dict[str, Any],
) -> tuple[EngineScenario, USDrawdownYearInput]:
    if isinstance(scenario_or_inputs, EngineScenario):
        if scenario_or_inputs.engine != ENGINE_ID:
            raise ValueError(
                f"Unsupported US drawdown engine: {scenario_or_inputs.engine}"
            )
        inputs = USDrawdownYearInput.model_validate(scenario_or_inputs.inputs)
        return scenario_or_inputs, inputs
    scenario = build_us_drawdown_year_scenario(scenario_or_inputs)
    return scenario, USDrawdownYearInput.model_validate(scenario.inputs)


_DRAW_TREATMENT = {
    "traditional": (
        "taxable IRA distribution of the owner (taxable_ira_distributions); "
        "unearned income for SNAP and SSI"
    ),
    "roth": (
        "qualified Roth distribution of the owner (tax_exempt_ira_distributions): "
        "untaxed, but unearned income for SNAP and SSI"
    ),
    "taxable": (
        "sale of investments: the gain share is long-term capital gain, the rest "
        "returns basis"
    ),
    "cash": "spending cash savings, which is not income",
}


def _assumptions(
    inputs: USDrawdownYearInput, result: USDrawdownYearResult
) -> dict[str, Any]:
    return {
        "currency": "USD",
        "tax_year": inputs.tax_year,
        "state": inputs.state,
        "filing_status": inputs.filing_status,
        "household": (
            "a married couple filing jointly"
            if inputs.spouse is not None
            else "one person filing single"
        ),
        "tax_and_benefit_engine": "policyengine-us",
        "draw_treatment": _DRAW_TREATMENT[inputs.draw_source],
        "taxable_gain_share": result.assumptions.taxable_gain_share_applied,
        "money_to_spend_definition": (
            "income entered plus the draw, less taxes before refundable credits, "
            "plus benefits and refundable credits; equal to PolicyEngine-US "
            "household_net_income plus the part of the draw that isn't income, "
            "with health benefits and costs left out"
        ),
        "savings_tested": (
            "balances on 1 January 2026; retirement accounts count toward "
            "ssi_countable_resources (POMS SI 01120.210 B), and SNAP leaves "
            "them out"
        ),
        "household_income_and_savings_owner": "the first person",
        "medicare_premium_year": inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS,
        "medicare_lines_and_amounts_year": result.medicare_surcharge.rates_year,
        "medicare_part_d": "everyone on Medicare is taken to have Part D",
        "dividends": "qualified",
        "capital_gains": "long-term",
        "roth_withdrawals": "qualified distributions",
    }


def _sources(versions: dict[str, str]) -> list[ModelSource]:
    return [
        ModelSource(
            name="PolicyEngine US",
            url="https://github.com/PolicyEngine/policyengine-us",
            version=versions["policyengine-us"],
            notes=(
                "Computes federal and state income taxes, SNAP, SSI and other "
                "benefits, Medicaid and Medicare Savings Program eligibility, and "
                "Medicare's income-related premiums."
            ),
        ),
        ModelSource(
            name="PolicyEngine Core",
            url="https://github.com/PolicyEngine/policyengine-core",
            version=versions["policyengine-core"],
            notes="Microsimulation framework used by PolicyEngine US.",
        ),
        ModelSource(
            name="IRS Uniform Lifetime Table",
            url="https://www.irs.gov/publications/p590b",
            notes="Sets the 2026 required minimum distributions (26 CFR 1.401(a)(9)-9).",
        ),
    ]


def caveats_for(
    inputs: USDrawdownYearInput, result: USDrawdownYearResult | None = None
) -> list[str]:
    """What this result leaves out, specific to these inputs where it can be."""
    caveats = [
        "We give educational estimates, not financial, tax or legal advice or a benefits decision.",
        "We cover one person filing single or a married couple filing jointly, everyone 65 or older by the end of 2026.",
        "We don’t ask where in your state you live, so local income taxes follow PolicyEngine-US’s defaults.",
        "We count savings at their 1 January 2026 balances for the whole year, so spending them down doesn’t change what you qualify for here.",
        "We count IRA and 401(k) balances as resources for SSI, and for the Medicaid and Medicare Savings Program tests that use SSI’s resource figure, because you can withdraw them (POMS SI 01120.210 B).",
        "We count every IRA and 401(k) withdrawal as income spread over the year, as PolicyEngine-US does for SNAP and SSI. SNAP leaves nonrecurring lump sums out of income and counts them as resources (7 CFR 273.9(c)(8)), so a single large withdrawal may count as savings instead.",
        "We take Social Security as the amount you enter, before Medicare premiums, and don’t apply the retirement earnings test.",
        "We don’t count the value of Medicaid or the Medicare Savings Programs; we mark where you would lose them.",
        f"Medicare premiums in {inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS} depend on {inputs.tax_year} income (42 USC 1395r(i)(4)). We apply CMS’s income lines and amounts for {result.medicare_surcharge.rates_year if result else inputs.tax_year}; the lines rise with inflation each year (42 USC 1395r(i)(5)), so the real {inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS} lines will be higher.",
        "We assume everyone on Medicare has Part D drug coverage and so pays its income-related amount too.",
        "We treat every dividend as qualified.",
    ]
    if inputs.draw_source == "roth" or any(
        person.roth_balance > 0 for _, person in inputs.people
    ):
        caveats.append(
            "We treat Roth withdrawals as qualified distributions, free of tax, which needs the first Roth contribution to be five or more years old (26 USC 408A(d)(2))."
        )
    if inputs.draw_source == "taxable":
        caveats.append(
            "We treat the gain on investments sold as long-term, so the lower capital gains rates apply."
        )
    minimums = result.required_minimums if result else []
    if minimums:
        caveats.append(
            "We figure required minimum distributions from the Uniform Lifetime Table. In the first year one is due, it can wait until 1 April of the next year."
        )
        if inputs.spouse is not None and (
            abs(inputs.you.birth_year - inputs.spouse.birth_year) > _JOINT_TABLE_AGE_GAP
        ):
            caveats.append(
                "When a spouse more than 10 years younger is the sole beneficiary, the Joint and Last Survivor Table applies and gives a smaller required minimum."
            )
    if any(minimum.shortfall > 0 for minimum in minimums):
        caveats.append(
            "Taking less than the required minimum brings an excise tax of 25% of the shortfall, or 10% if corrected in time (26 USC 4974); this result doesn’t add it to your taxes."
        )
    return caveats
