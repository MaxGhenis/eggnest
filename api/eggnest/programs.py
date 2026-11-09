"""Agent-facing program catalog for EggNest calculation surfaces."""

from __future__ import annotations

from .models import ProgramOutput, ProgramSpec
from .models_uk import UKSimulationResult
from .models_uk_drawdown import UKDrawdownYearResult
from .models_us_drawdown import USDrawdownYearResult

PROGRAMS: list[ProgramSpec] = [
    ProgramSpec(
        id="us_household_resources",
        display_name="US household resources",
        country="USA",
        jurisdiction="us",
        scope=(
            "Annual household taxes, credits, selected benefits, and net resources "
            "for a US household."
        ),
        engine="us_household_resources",
        cli="eggnest household run household.yaml --output-format envelope",
        primary_output="household_resources_result.net_income",
        outputs=[
            ProgramOutput(
                name="net_income",
                label="Net household resources",
                kind="scalar",
                unit="USD/year",
                description=(
                    "Gross income minus modeled taxes plus modeled benefits; equals "
                    "PolicyEngine-US household_net_income without health coverage."
                ),
            ),
            ProgramOutput(
                name="total_taxes",
                label="Total taxes",
                kind="scalar",
                unit="USD/year",
                description=(
                    "All taxes before refundable credits: federal income tax after "
                    "non-refundable credits, state and local income taxes, state "
                    "use tax, local occupational taxes, employee payroll taxes "
                    "(including state payroll taxes), and self-employment tax."
                ),
            ),
            ProgramOutput(
                name="total_benefits",
                label="Total benefits",
                kind="scalar",
                unit="USD/year",
                description=(
                    "Modeled benefits other than Social Security and health "
                    "coverage, federal and state refundable tax credits, and the "
                    "Alaska Permanent Fund Dividend, returned by PolicyEngine-US."
                ),
            ),
            ProgramOutput(
                name="marginal_tax_rate",
                label="Marginal tax rate",
                kind="scalar",
                unit="rate",
                description=(
                    "Share of $1,000 more annual wages for the primary earner "
                    "that does not reach net income, including benefit and credit "
                    "phase-outs."
                ),
            ),
        ],
        caveats=[
            "Policy logic is delegated to PolicyEngine-US.",
            "Current household surface captures annual income and the benefits PolicyEngine-US models; detailed monthly expenses are not yet modeled.",
            "Health coverage is excluded from net income.",
            "The household input has no county, so PolicyEngine-US places the household in the alphabetically first county in its state (for example Albany County, NY, or Alameda County, CA); county- and city-specific rules are that county's, so New York City income tax and city wage taxes such as Philadelphia's do not apply.",
        ],
    ),
    ProgramSpec(
        id="us_retirement",
        display_name="US retirement simulation",
        country="USA",
        jurisdiction="us",
        scope="Monte Carlo retirement outcomes with PolicyEngine-US tax calculations.",
        engine="us_retirement",
        cli="eggnest core run scenario.yaml --engine us_retirement --output-format envelope",
        primary_output="us_simulation_result.success_rate",
        outputs=[
            ProgramOutput(
                name="success_rate",
                label="Modeled success rate",
                kind="scalar",
                unit="rate",
                description="Share of paths that avoid depletion before death or horizon.",
            ),
            ProgramOutput(
                name="median_final_value",
                label="Median final portfolio value",
                kind="scalar",
                unit="USD",
                description=(
                    "Median portfolio value at the end of the modeled horizon, "
                    "in cash terms (the engine is nominal)."
                ),
            ),
        ],
        caveats=["Educational calculator output only; not financial advice."],
    ),
    ProgramSpec(
        id="uk_retirement",
        display_name="UK retirement simulation",
        country="GBR",
        jurisdiction="uk",
        scope="UK ISA/SIPP/GIA retirement outcomes with PolicyEngine UK tax calculations.",
        engine="uk_retirement",
        cli="eggnest core run scenario.yaml --engine uk_retirement --output-format envelope",
        primary_output="uk_simulation_result.success_rate",
        outputs=[
            ProgramOutput(
                name="success_rate",
                label="Modeled success rate",
                kind="scalar",
                unit="rate",
                # One definition: the result model's own field description.
                description=UKSimulationResult.model_fields["success_rate"].description,
            ),
            ProgramOutput(
                name="median_final_value",
                label="Median final portfolio value",
                kind="scalar",
                unit="GBP",
                description=(
                    "Median portfolio value at the end of the modeled horizon, "
                    "in cash terms."
                ),
            ),
            ProgramOutput(
                name="median_final_value_real",
                label="Median final portfolio value in today's money",
                kind="scalar",
                unit="GBP",
                description=(
                    "median_final_value deflated by each simulated year's median "
                    "inflation, compounded; the UK simulator page shows this figure."
                ),
            ),
        ],
        caveats=["Educational calculator output only; not financial advice."],
    ),
    ProgramSpec(
        id="uk_drawdown_year",
        display_name="UK drawdown year",
        country="GBR",
        jurisdiction="uk",
        scope=(
            "What drawing a chosen amount from a pension pot, ISA, GIA or cash "
            "costs one person in income tax, National Insurance and Pension "
            "Credit over the 2026/27 tax year, across every draw that pot allows."
        ),
        engine="uk_drawdown_year",
        cli=(
            "eggnest core run scenario.yaml --engine uk_drawdown_year "
            "--output-format envelope"
        ),
        primary_output="uk_drawdown_year_result.money_to_spend",
        outputs=[
            ProgramOutput(
                name="money_to_spend",
                label="Money to spend",
                kind="scalar",
                unit="GBP/year",
                description=UKDrawdownYearResult.model_fields["at_chosen_draw"]
                .annotation.model_fields["money_to_spend"]
                .description,
            ),
            ProgramOutput(
                name="pension_credit",
                label="Pension Credit",
                kind="scalar",
                unit="GBP/year",
                description=(
                    "Guarantee credit for one person, with an undrawn pot counted "
                    "at the annuity income it could buy."
                ),
            ),
            ProgramOutput(
                name="next_1000",
                label="Where the next £1,000 goes",
                kind="object",
                unit="share",
                description=(
                    "Shares of the next £1,000 of draw kept, paid in tax and lost "
                    "in Pension Credit; they add to 1."
                ),
            ),
        ],
        caveats=[
            "Needs the Axiom rules engine and a rulespec-uk checkout.",
            "Covers one person living alone and leaves out Savings Credit, Housing Benefit and Council Tax Reduction.",
            "Doesn't cover Scottish taxpayers.",
        ],
    ),
    ProgramSpec(
        id="us_drawdown_year",
        display_name="US drawdown year",
        country="USA",
        jurisdiction="us",
        scope=(
            "What drawing a chosen amount from a traditional IRA or 401(k), a "
            "Roth IRA, taxable investments or cash costs a single person or a "
            "married couple, everyone 65 or older, in 2026 federal and state "
            "income tax and in benefits, and how it moves their Medicare "
            "premiums in 2028, across every draw that account allows."
        ),
        engine="us_drawdown_year",
        cli=(
            "eggnest core run scenario.yaml --engine us_drawdown_year "
            "--output-format envelope"
        ),
        primary_output="us_drawdown_year_result.money_to_spend",
        outputs=[
            ProgramOutput(
                name="money_to_spend",
                label="Money to spend",
                kind="scalar",
                unit="USD/year",
                description=USDrawdownYearResult.model_fields["at_chosen_draw"]
                .annotation.model_fields["money_to_spend"]
                .description,
            ),
            ProgramOutput(
                name="benefits",
                label="Benefits",
                kind="scalar",
                unit="USD/year",
                description=USDrawdownYearResult.model_fields["at_chosen_draw"]
                .annotation.model_fields["benefits"]
                .description,
            ),
            ProgramOutput(
                name="medicare_surcharge",
                label="Medicare surcharge two years on",
                kind="object",
                unit="USD/year",
                description=(
                    "Part B and Part D income-related premiums this year's "
                    "income sets for 2028, at the latest lines CMS has set."
                ),
            ),
            ProgramOutput(
                name="next_1000",
                label="Where the next $1,000 goes",
                kind="object",
                unit="share",
                description=(
                    "Shares of the next $1,000 of draw kept, paid in tax and lost "
                    "in benefits; they add to 1."
                ),
            ),
        ],
        caveats=[
            "Covers one person filing single or a married couple filing jointly, everyone 65 or older by the end of 2026.",
            "Counts savings at their 1 January 2026 balances and doesn't count the value of Medicaid or the Medicare Savings Programs.",
            "Applies the latest Medicare income lines CMS has set to 2028 premiums.",
        ],
    ),
]


def list_programs(jurisdiction: str | None = None) -> list[ProgramSpec]:
    """Return programs available to agent callers."""
    if jurisdiction is None:
        return PROGRAMS
    normalized = jurisdiction.lower()
    return [
        program
        for program in PROGRAMS
        if program.jurisdiction.lower() == normalized
        or program.country.lower() == normalized
    ]
