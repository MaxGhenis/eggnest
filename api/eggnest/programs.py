"""Agent-facing program catalog for EggNest calculation surfaces."""

from __future__ import annotations

from .models import ProgramOutput, ProgramSpec

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
                description="Median portfolio value at the end of the modeled horizon.",
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
                description="Share of paths that avoid depletion before death or horizon.",
            ),
            ProgramOutput(
                name="median_final_wealth",
                label="Median final wealth",
                kind="scalar",
                unit="GBP",
                description="Median final wealth at the end of the modeled horizon.",
            ),
        ],
        caveats=["Educational calculator output only; not financial advice."],
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
