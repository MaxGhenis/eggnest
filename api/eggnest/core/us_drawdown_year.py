"""Core envelope for the one-year US drawdown calculator."""

from __future__ import annotations

from importlib.metadata import version as package_version
from typing import Any

from eggnest import __version__
from eggnest.drawdown_us import citations, run_us_drawdown_year
from eggnest.models_us_drawdown import (
    MEDICARE_AGE,
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
        "taxable distribution of the owner from {account}; "
        "unearned income for SNAP; for SSI and the programs that use its income "
        "rules, Eggnest reads it as a resource changing form, not income "
        "(20 CFR 416.1103(c))"
    ),
    "roth": (
        "qualified Roth distribution of the owner (tax_exempt_ira_distributions): "
        "untaxed, but unearned income for SNAP; for SSI and the programs that "
        "use its income rules, Eggnest reads it as a resource changing form, "
        "not income (20 CFR 416.1103(c))"
    ),
    "taxable": (
        "sale of investments: the gain share is long-term capital gain, the rest "
        "returns basis"
    ),
    "cash": "spending cash savings, which is not income",
}


_TRADITIONAL_ACCOUNTS = {
    "ira": "an IRA (taxable_ira_distributions)",
    "workplace_plan": (
        "a workplace plan such as a 401(k) or 403(b) (taxable_401k_distributions)"
    ),
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
        "draw_treatment": _DRAW_TREATMENT[inputs.draw_source].format(
            account=_TRADITIONAL_ACCOUNTS[inputs.draw_account]
        ),
        "taxable_gain_share": result.assumptions.taxable_gain_share_applied,
        "money_to_spend_definition": (
            "the income the household enters plus the draw, less taxes before "
            "refundable credits, plus benefits and refundable credits; it equals "
            "PolicyEngine-US household_net_income plus the part of the draw that "
            "isn't income, without health benefits or costs, except on Wisconsin's "
            "retirement income exclusion path, where it exceeds that by the tax "
            "the path saves"
        ),
        "savings_tested": (
            "balances on January 1, 2026, held all year; retirement accounts "
            "count toward ssi_countable_resources at their full balance (POMS "
            "SI 01120.210 A.3, B, D.2), and SNAP leaves them out"
        ),
        "policyengine_us_reform": (
            "retirement_distributions, interest_income and dividend_income "
            "taken out of SSI's unearned income sources "
            "(gov.ssa.ssi.income.sources.unearned): Eggnest reads a withdrawal "
            "from an account counted as a resource as a resource changing form, "
            "not income (20 CFR 416.1103(c), 416.1207(e); POMS SI 01110.600 "
            "B.4, SI 01120.250 B.2), and SSI excludes interest and dividends on "
            "countable resources (42 USC 1382a(b)(23); 20 CFR 416.1124(c)(22))"
        ),
        "household_income_owner": (
            "split evenly between the spouses on a joint return; the filer otherwise"
        ),
        "household_savings_owner": "the first person",
        "medicare_premium_year": inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS,
        "medicare_lines_and_amounts_year": result.medicare_surcharge.rates_year,
        "medicare_part_d": "we assume everyone on Medicare has Part D",
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
            notes="The microsimulation framework PolicyEngine US runs on.",
        ),
        ModelSource(
            name="IRS Uniform Lifetime Table",
            url="https://www.irs.gov/publications/p590b",
            notes="Gives the divisors for the 2026 required minimum distributions (26 CFR 1.401(a)(9)-9).",
        ),
    ]


def _ssi_caveats(inputs: USDrawdownYearInput) -> list[str]:
    """Where SSI's rules, and those of the programs that follow them, may
    differ from what we count for these inputs."""
    caveats = []
    people = inputs.people
    if any(person.traditional_balance > 0 for _, person in people):
        caveats.append(
            "If a workplace plan entitles you to an annuity or other regular payments, SSA requires you to apply for them and choose them over a lump sum. It may then leave the plan out of your resources and count the payments as income (POMS SI 01120.210 B, E.1; SI 00830.160 B.1). Taking a lump sum instead can make you ineligible for SSI for that month (POMS SI 00510.001 D.4). We don’t model that."
        )
    for who, person in people:
        if person.earnings <= 0 or person.traditional_balance <= 0:
            continue
        if who == "spouse":
            part = "your spouse’s traditional balance is in a plan at their current job that pays nothing until they leave"
        else:
            part = "your traditional balance is in a plan at your current job that pays nothing until you leave"
        caveats.append(
            f"If part of {part}, SSI doesn’t count that part as a resource (POMS SI 01120.210 C.1). We count the whole balance."
        )
    for who, person in people:
        if person.age != MEDICARE_AGE:
            continue
        whom = "your spouse" if who == "spouse" else "you"
        caveats.append(
            f"PolicyEngine-US treats {whom} as 65 for all of {inputs.tax_year}. SSI decides each month (20 CFR 416.420) and counts someone as aged only once they are 65 (20 CFR 416.202(a)(1)), and Medicare’s hospital insurance starts the same way (42 USC 426(a)), so the SSI, Medicaid and Medicare Savings Program results here can include months before that birthday."
        )
    savings = (
        inputs.cash_savings
        + inputs.taxable_balance
        + sum(person.traditional_balance + person.roth_balance for _, person in people)
    )
    investment_income = (
        inputs.taxable_interest + inputs.tax_exempt_interest + inputs.dividends
    )
    if investment_income > 0 and inputs.cash_savings + inputs.taxable_balance <= 0:
        caveats.append(
            "SSI leaves out interest and dividends only when they come from savings it counts (42 USC 1382a(b)(23)), and we leave out all you enter. You entered interest or dividends but no cash or investments, so enter the savings they come from, or SSI here may be too high."
        )
    if inputs.state == "CO" and inputs.spouse is not None and savings > 0:
        caveats.append(
            "Colorado adds up a couple’s savings for the Old Age Pension’s limit (9 CCR 2503-5 3.520.72 A), but PolicyEngine-US tests each spouse’s own savings against it. We put the cash and investments you share on you, so the page can show an Old Age Pension for one of you that Colorado wouldn’t pay."
        )
    return caveats


def caveats_for(
    inputs: USDrawdownYearInput, result: USDrawdownYearResult | None = None
) -> list[str]:
    """What this result leaves out, specific to these inputs where it can be."""
    premium_year = inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS
    rates_year = result.medicare_surcharge.rates_year if result else inputs.tax_year
    medicare = (
        f"Social Security uses your {inputs.tax_year} income to set the extra you pay "
        f"for Medicare in {premium_year} (42 USC 1395r(i)(4)). We apply Medicare’s "
        f"{rates_year} income lines and amounts."
    )
    if rates_year < premium_year:
        medicare += (
            " Medicare raises the lines with inflation, as the law requires "
            f"(42 USC 1395r(i)(5)), so its {premium_year} lines will exceed these."
        )
    caveats = [
        "We give educational estimates, not financial, tax or legal advice or a benefits decision.",
        "We cover one person filing single or a married couple filing jointly, everyone 65 or older by the end of 2026.",
        "We don’t ask where in your state you live, so PolicyEngine-US places you in your state’s alphabetically first county and applies that county’s rules, including any local income tax.",
        "We count savings at their balances on January 1, 2026, for the whole year. So the savings tests for SSI, Medicaid and the Medicare Savings Programs treat what you withdraw as still in your accounts, while money to spend counts it as spent. SSI looks at your savings on the first of each month (20 CFR 416.1207(a)), so spending them down could qualify you in later months, which we don’t show.",
        "We count IRA and 401(k) balances as resources for SSI, and for the Medicaid and Medicare Savings Program tests that use SSI’s resource figure, because you can withdraw them. SSA counts what you could withdraw now, less any penalty your plan charges for that, without taking off the income tax you would owe (POMS SI 01120.210 A.3, B, D.2). We count the whole balance.",
        "SSI, and the Medicare Savings Programs and Medicaid for people 65 and older that follow SSI’s income rules, don’t count as income what you get for a resource: it is the resource in another form (20 CFR 416.1103(c)). We read a withdrawal from a retirement account the same way. SSA’s rules say so in words only for Trump Accounts, a kind of IRA, and for withdrawals by a spouse not on SSI whose income SSA counts toward yours (POMS SI 01120.250 B.2, SI 01330.120 C.2). SSI also leaves out interest and dividends earned on savings it counts (42 USC 1382a(b)(23)). PolicyEngine-US counts withdrawals, interest and dividends as SSI income, so we change those rules when we run it.",
        "For SNAP we count every IRA and 401(k) withdrawal as income and spread it over the year, as PolicyEngine-US does. State SNAP agencies count a nonrecurring lump sum as a resource rather than income (7 CFR 273.9(c)(8)), so a single large withdrawal may count as savings instead.",
        "We take Social Security as the amount you enter, before Medicare premiums, and don’t apply the retirement earnings test.",
        "We don’t count the value of Medicaid or the Medicare Savings Programs; we mark where you would lose them.",
        medicare,
        "We assume everyone on Medicare has Part D drug coverage and so pays its income-related amount too.",
        "We treat every dividend as qualified.",
    ]
    caveats.extend(_ssi_caveats(inputs))
    if inputs.draw_source == "roth" or any(
        person.roth_balance > 0 for _, person in inputs.people
    ):
        caveats.append(
            "We treat Roth withdrawals as tax-free qualified distributions, as the IRS does from the fifth tax year after the year of your first Roth contribution (26 USC 408A(d)(2))."
        )
    if inputs.draw_source == "taxable":
        caveats.append(
            "We treat the gain on investments you sell as long-term and apply the lower long-term capital gains rates to it."
        )
    minimums = result.required_minimums if result else []
    if minimums:
        caveats.append(
            "We figure required minimum distributions from the IRS Uniform Lifetime Table, on each person’s whole traditional balance. You can take an IRA’s minimum from any of your IRAs, but each workplace plan, such as a 401(k), must pay out its own (26 CFR 1.408-8(e))."
        )
        if any(minimum.first_year for minimum in minimums):
            caveats.append(
                f"In the first year you owe a minimum, the year you turn 73, you can wait until April 1, {inputs.tax_year + 1}, to take it, and you then take your {inputs.tax_year + 1} minimum by the end of {inputs.tax_year + 1} as well (26 USC 401(a)(9)(C)). We count only what you take in {inputs.tax_year}."
            )
        for minimum in minimums:
            if inputs.person(minimum.person).earnings <= 0:
                continue
            if minimum.person == "spouse":
                who = "your spouse still works for the employer whose plan holds part of their balance, and owns"
            else:
                who = "you still work for the employer whose plan holds part of your balance, and own"
            caveats.append(
                f"If {who} 5% or less of the business, that plan’s minimum can wait until April 1 of the year after retirement (26 USC 401(a)(9)(C)). IRAs get no such delay, and we figure the minimum on the whole balance."
            )
        if inputs.spouse is not None:
            # How much older each owner is than the other, in years at the end
            # of the tax year.
            older_by = {
                "you": inputs.spouse.birth_year - inputs.you.birth_year,
                "spouse": inputs.you.birth_year - inputs.spouse.birth_year,
            }
            for minimum in minimums:
                if older_by[minimum.person] <= _JOINT_TABLE_AGE_GAP:
                    continue
                if minimum.person == "spouse":
                    who = "your spouse names you, more than 10 years younger, as their sole beneficiary, they use the IRS Joint and Last Survivor Table for their minimum instead"
                else:
                    who = "you name your spouse, more than 10 years younger, as your sole beneficiary, you use the IRS Joint and Last Survivor Table for your minimum instead"
                caveats.append(
                    f"If {who}. It gives a smaller required minimum than we show (26 CFR 1.401(a)(9)-9)."
                )
    if any(minimum.shortfall > 0 and not minimum.first_year for minimum in minimums):
        caveats.append(
            "If you take less than your required minimum, you owe an excise tax of 25% of the shortfall, or 10% if you correct it in time (26 USC 4974). We leave it out of your taxes and money to spend."
        )
    return caveats
