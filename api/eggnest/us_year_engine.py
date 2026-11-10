"""PolicyEngine-US: one household's year at many draw amounts in one run.

The calculator asks what a household's year looks like at a few hundred draw
amounts. This module builds one PolicyEngine-US household per draw amount in a
single simulation, so a whole sweep costs about as much as one household.

It decides what each PolicyEngine-US input holds (``build_situation``):

- A traditional IRA or 401(k) draw is the owner's ``taxable_ira_distributions``,
  on top of their other traditional withdrawals.
- A Roth draw is the owner's ``tax_exempt_ira_distributions``: a qualified
  distribution, untaxed but counted by SNAP and SSI as unearned income.
- Selling taxable investments realizes ``long_term_capital_gains`` on the gain
  share of the sale. The rest returns basis, which no program counts as income.
- Spending cash savings is not income.
- Retirement accounts count toward ``ssi_countable_resources`` at their full
  balance, since their owners can withdraw a lump sum (POMS SI 01120.210 B).
  That figure feeds the SSI resource test and the Medicaid and Medicare
  Savings Program tests that use SSI's method. SNAP leaves retirement accounts
  out (``snap_assets`` reads only bank, stock and bond assets).
- Household-level income and savings (interest, dividends, brokerage and
  cash balances) belong to the first person.

The accounting follows ``eggnest.household``: taxes before refundable
credits, the state tax on Wisconsin's retirement income exclusion path when
that path wins, refundable credits counted once as benefits, and Social
Security and health coverage left out of benefits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version as package_version

import numpy as np

from .constants import STATE_FIPS
from .models_us_drawdown import (
    MEDICARE_PREMIUM_LAG_YEARS,
    USDrawdownPerson,
    USDrawdownYearInput,
)

ENGINE = "policyengine-us"

# Amounts smaller than this are zero.
CENT = 0.005
# PolicyEngine-US computes in float32. A remainder smaller than 4 ulps of the
# amounts it came from, or $1, is rounding rather than a missing item.
FLOAT32_RELATIVE_ROUNDING = 4 * 2**-24
ROUNDING = 1.0

# household_benefits entries that are not money to spend here: Social Security
# is entered income, and health coverage is left out of net income.
EXCLUDED_BENEFITS = frozenset({"social_security", "household_health_benefits"})

# Health coverage whose end the calculator marks without counting its value:
# name -> (PolicyEngine-US variable, which is positive while covered).
COVERAGE_VARIABLES = {
    "medicaid": "is_medicaid_eligible",
    "msp": "msp",
}

# What other taxes hold, as eggnest.household itemizes them: employee FICA
# (payroll_tax), state payroll and self-employment tax, then the rest of
# household_tax_before_refundable_credits by PolicyEngine-US variable, with
# anything left over as other_taxes.
_NAMED_REST = (
    "state_use_tax",
    "local_income_tax_before_refundable_credits",
    "local_occupational_tax",
    # Zero under current law; a PolicyEngine-US reform can add it.
    "flat_tax",
)
OTHER_TAX_PARTS = (
    "payroll_tax",
    "state_payroll_tax",
    "self_employment_tax",
    *_NAMED_REST,
    "other_taxes",
)


def engine_label() -> str:
    return f"{ENGINE} {package_version('policyengine-us')}"


def _rounding(scale: np.ndarray) -> np.ndarray:
    return np.maximum(ROUNDING, FLOAT32_RELATIVE_ROUNDING * np.abs(scale))


def reported_draw(inputs: USDrawdownYearInput, draws: np.ndarray) -> np.ndarray:
    """The part of each draw PolicyEngine-US sees as market income."""
    if inputs.draw_source in ("traditional", "roth"):
        return np.asarray(draws, dtype=float)
    if inputs.draw_source == "taxable":
        return np.asarray(draws, dtype=float) * inputs.taxable_gain_share
    return np.zeros(len(draws))


def entered_market_income(inputs: USDrawdownYearInput, draws: np.ndarray) -> np.ndarray:
    """Market income the household entered, by PolicyEngine-US's definition."""
    base = sum(
        person.pension_income
        + person.government_pension_income
        + person.earnings
        + person.other_traditional_withdrawals
        for _, person in inputs.people
    )
    base += inputs.taxable_interest + inputs.tax_exempt_interest + inputs.dividends
    return base + reported_draw(inputs, draws)


def _person_inputs(
    inputs: USDrawdownYearInput,
    who: str,
    person: USDrawdownPerson,
    draw: float,
) -> dict:
    year = str(inputs.tax_year)
    later = str(inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS)
    owns_draw = inputs.draw_owner == who
    traditional = person.other_traditional_withdrawals + (
        draw if owns_draw and inputs.draw_source == "traditional" else 0.0
    )
    roth = draw if owns_draw and inputs.draw_source == "roth" else 0.0
    role = "is_tax_unit_head" if who == "you" else "is_tax_unit_spouse"
    values: dict = {
        "age": {year: person.age, later: person.age + MEDICARE_PREMIUM_LAG_YEARS},
        role: {year: True, later: True},
        "social_security_retirement": {year: person.social_security},
        "taxable_private_pension_income": {year: person.pension_income},
        "taxable_public_pension_income": {year: person.government_pension_income},
        "employment_income": {year: person.earnings},
        "taxable_ira_distributions": {year: traditional},
        "tax_exempt_ira_distributions": {year: roth},
        "taxable_roth_conversions": {year: person.roth_conversion},
    }
    resources = person.traditional_balance + person.roth_balance
    if who == "you":
        gain = (
            draw * inputs.taxable_gain_share if inputs.draw_source == "taxable" else 0.0
        )
        values.update(
            {
                "taxable_interest_income": {year: inputs.taxable_interest},
                "tax_exempt_interest_income": {year: inputs.tax_exempt_interest},
                "qualified_dividend_income": {year: inputs.dividends},
                "long_term_capital_gains": {year: gain},
                "bank_account_assets": {year: inputs.cash_savings},
                "stock_assets": {year: inputs.taxable_balance},
            }
        )
        resources += inputs.cash_savings + inputs.taxable_balance
    values["ssi_countable_resources"] = {year: resources}
    return values


def build_situation(inputs: USDrawdownYearInput, draws: np.ndarray) -> dict:
    """One PolicyEngine-US household per draw amount, in draw order."""
    year = str(inputs.tax_year)
    later = str(inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS)
    joint = inputs.filing_status == "married_filing_jointly"
    filing_status = "JOINT" if joint else "SINGLE"
    state_fips = STATE_FIPS[inputs.state]
    situation: dict = {
        "people": {},
        "households": {},
        "tax_units": {},
        "spm_units": {},
        "families": {},
        "marital_units": {},
    }
    for index, draw in enumerate(np.asarray(draws, dtype=float)):
        members = []
        for who, person in inputs.people:
            person_id = f"{who}_{index}"
            members.append(person_id)
            situation["people"][person_id] = _person_inputs(
                inputs, who, person, float(draw)
            )
        situation["households"][f"household_{index}"] = {
            "members": members,
            "state_fips": {year: state_fips, later: state_fips},
        }
        situation["tax_units"][f"tax_unit_{index}"] = {
            "members": members,
            "filing_status": {year: filing_status, later: filing_status},
        }
        for group in ("spm_units", "families", "marital_units"):
            situation[group][f"{group}_{index}"] = {"members": list(members)}
    return situation


@dataclass
class USYearArrays:
    """A household's year at each draw amount; each array has one value per draw.

    Taxes and benefits are household totals in dollars for the tax year.
    ``other_tax_parts`` splits ``other_taxes`` by the keys ``OTHER_TAX_PARTS``
    names; an engine that doesn't itemize them leaves it empty.
    """

    federal_income_tax: np.ndarray
    state_income_tax: np.ndarray
    other_taxes: np.ndarray
    benefits: np.ndarray
    programs: dict[str, np.ndarray]
    taxable_social_security: np.ndarray
    medicare_income: np.ndarray
    later_medicare_surcharge: np.ndarray
    coverage: dict[str, np.ndarray] = field(default_factory=dict)
    other_tax_parts: dict[str, np.ndarray] = field(default_factory=dict)
    people_on_medicare: int = 0
    medicare_lines: list[float] = field(default_factory=list)
    medicare_rates_year: int = 0

    @property
    def taxes(self) -> np.ndarray:
        return self.federal_income_tax + self.state_income_tax + self.other_taxes


class PolicyEngineUSYear:
    """Evaluates a household's year with PolicyEngine-US."""

    name = ENGINE

    def label(self) -> str:
        return engine_label()

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        from policyengine_us import Simulation

        draws = np.asarray(draws, dtype=float)
        sim = Simulation(situation=build_situation(inputs, draws))
        year = inputs.tax_year
        later = year + MEDICARE_PREMIUM_LAG_YEARS

        def household(variable: str, period: int = year) -> np.ndarray:
            return np.asarray(
                sim.calculate(variable, period, map_to="household"), dtype=float
            )

        # Taxes, all before refundable credits.
        federal = household("income_tax_before_refundable_credits")
        state_after_credits = household("state_income_tax")
        state_before_credits = household("state_income_tax_before_refundable_credits")
        state_credits = household("household_refundable_state_tax_credits")
        # state_income_tax is the tax after refundable credits, except on an
        # election path the before-credit figure ignores (Wisconsin's
        # retirement income exclusion), which forfeits the credits. float32
        # rounding must not look like an election.
        tolerance = CENT + FLOAT32_RELATIVE_ROUNDING * np.abs(state_before_credits)
        election = state_after_credits < (
            state_before_credits - state_credits - tolerance
        )
        state = np.where(
            election, np.maximum(state_after_credits, 0.0), state_before_credits
        )
        state_credits = np.where(
            election, np.maximum(-state_after_credits, 0.0), state_credits
        )
        employee_payroll = household("employee_payroll_tax")
        state_payroll = household("employee_state_payroll_tax")
        self_employment = household("self_employment_tax")
        payroll = employee_payroll + self_employment
        household_tax = household("household_tax_before_refundable_credits")
        # State use tax and local taxes: the rest of the household's tax, by
        # PolicyEngine-US variable, and whatever remains beyond float32 rounding.
        named = {name: household(name) for name in _NAMED_REST}
        unnamed = (
            household_tax
            - federal
            - state_before_credits
            - payroll
            - sum(named.values(), np.zeros(len(draws)))
        )
        unnamed = np.where(np.abs(unnamed) < _rounding(household_tax), 0.0, unnamed)
        other_tax_parts = {
            "payroll_tax": employee_payroll - state_payroll,
            "state_payroll_tax": state_payroll,
            "self_employment_tax": self_employment,
            **named,
            "other_taxes": unnamed,
        }

        # Benefits: household_benefits without Social Security and health
        # coverage, plus market income PolicyEngine computes that the household
        # didn't enter (the Alaska Permanent Fund Dividend), plus refundable
        # credits.
        parameters = sim.tax_benefit_system.parameters(f"{year}-01-01")
        all_benefits = household("household_benefits")
        non_credit = (
            all_benefits
            - household("social_security")
            - household("household_health_benefits")
        )
        programs: dict[str, np.ndarray] = {}
        for program in parameters.gov.household.household_benefits:
            if program in EXCLUDED_BENEFITS:
                continue
            values = household(program)
            if np.any(np.abs(values) > CENT):
                programs[program] = values
        other_benefits = non_credit - sum(programs.values(), np.zeros(len(draws)))
        if np.any(np.abs(other_benefits) >= _rounding(all_benefits)):
            programs["other_benefits"] = other_benefits

        market_income = household("household_market_income")
        computed_income = market_income - entered_market_income(inputs, draws)
        computed_income = np.where(
            np.abs(computed_income) < _rounding(market_income), 0.0, computed_income
        )
        permanent_fund = household("ak_permanent_fund_dividend")
        if np.any(permanent_fund > CENT):
            programs["ak_permanent_fund_dividend"] = permanent_fund
        other_computed = computed_income - permanent_fund
        if np.any(np.abs(other_computed) >= _rounding(market_income)):
            programs["other_computed_income"] = other_computed

        federal_credits = household("income_tax_refundable_credits")
        if np.any(np.abs(federal_credits) > CENT):
            programs["income_tax_refundable_credits"] = federal_credits
        if np.any(np.abs(state_credits) > CENT):
            programs["household_refundable_state_tax_credits"] = state_credits
        benefits = non_credit + computed_income + federal_credits + state_credits

        coverage = {
            name: household(variable) > CENT
            for name, variable in COVERAGE_VARIABLES.items()
        }

        # Medicare premiums two years on, set by this year's income.
        enrolled = np.asarray(sim.calculate("medicare_enrolled", later), dtype=float)
        part_b = np.asarray(
            sim.calculate("gross_medicare_part_b_premium_if_enrolled", later),
            dtype=float,
        ) - enrolled * np.asarray(
            sim.calculate("base_part_b_premium", later), dtype=float
        )
        surcharge = sim.map_result(part_b, "person", "household") + household(
            "income_adjusted_part_d_premium_surcharge", later
        )
        people_on_medicare = int(
            round(float(sim.map_result(enrolled, "person", "household")[0]))
        )
        lines, rates_year = _medicare_lines(sim, inputs, later)

        return USYearArrays(
            federal_income_tax=federal,
            state_income_tax=state,
            other_taxes=sum(other_tax_parts.values(), np.zeros(len(draws))),
            benefits=benefits,
            programs=programs,
            taxable_social_security=household("taxable_social_security"),
            medicare_income=household("medicare_irmaa_magi_two_years_prior", later),
            later_medicare_surcharge=np.asarray(surcharge, dtype=float),
            coverage=coverage,
            other_tax_parts=other_tax_parts,
            people_on_medicare=people_on_medicare,
            medicare_lines=lines,
            medicare_rates_year=rates_year,
        )


def _medicare_lines(
    sim, inputs: USDrawdownYearInput, premium_year: int
) -> tuple[list[float], int]:
    """Where the income-related premium steps up, and the year those lines are from.

    PolicyEngine-US holds CMS's published lines and amounts and does not
    project them, so a premium year CMS hasn't set uses the latest year it has.
    """
    status = "joint" if inputs.filing_status == "married_filing_jointly" else "single"
    medicare = sim.tax_benefit_system.parameters.gov.hhs.medicare
    scales = [
        getattr(medicare.part_b.irmaa, status),
        getattr(medicare.part_d.irmaa, status),
    ]
    cutoff = f"{premium_year}-01-01"
    years = [
        int(value.instant_str[:4])
        for scale in scales
        for bracket in scale.brackets
        for parameter in (bracket.threshold, bracket.amount)
        for value in parameter.values_list
        if value.instant_str <= cutoff
    ]
    thresholds = scales[0](cutoff).thresholds
    return [float(line) for line in thresholds if line > 0], max(years)
