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
                description="Gross income minus modeled taxes plus modeled benefits.",
            ),
            ProgramOutput(
                name="total_taxes",
                label="Total taxes",
                kind="scalar",
                unit="USD/year",
                description=(
                    "Federal income tax before refundable credits, state income tax, "
                    "and payroll taxes."
                ),
            ),
            ProgramOutput(
                name="total_benefits",
                label="Total benefits",
                kind="scalar",
                unit="USD/year",
                description=(
                    "Modeled cash benefits and refundable tax credits returned by "
                    "PolicyEngine-US."
                ),
            ),
            ProgramOutput(
                name="marginal_tax_rate",
                label="Marginal tax rate",
                kind="scalar",
                unit="rate",
                description="Modeled tax change from $1,000 more annual earnings.",
            ),
        ],
        caveats=[
            "Policy logic is delegated to PolicyEngine-US.",
            "Current household surface captures annual income and selected benefits; detailed monthly expenses are not yet modeled.",
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
