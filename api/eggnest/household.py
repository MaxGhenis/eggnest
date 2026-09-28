"""Household tax and benefits calculator using PolicyEngine-US.

The rows follow PolicyEngine-US ``household_net_income``:

    net_income = total_income - total_taxes + total_benefits

- ``total_income`` is the income the user entered, including Social Security.
- ``total_taxes`` is ``household_tax_before_refundable_credits``: federal income
  tax after non-refundable credits, state income tax, payroll taxes and other
  taxes, all before refundable credits.
- ``total_benefits`` is ``household_benefits`` without Social Security (already
  in ``total_income``) and health coverage (excluded), plus federal and state
  refundable tax credits, plus market income PolicyEngine computes that the
  user did not enter (the Alaska Permanent Fund Dividend).

Refundable credits are counted once, as benefits. PolicyEngine's ``income_tax``
and ``state_income_tax`` already subtract them, so neither feeds a tax row.
"""

from policyengine_us import Simulation

from eggnest.constants import FILING_STATUS_PE_SITUATION, STATE_FIPS
from eggnest.models import (
    HouseholdInput,
    HouseholdResult,
    LifeEventComparison,
)

# household_benefits entries that are not added to total_benefits:
# Social Security is user input, already in total_income; health coverage is
# excluded from net income (PolicyEngine's default as well).
EXCLUDED_BENEFITS = frozenset({"social_security", "household_health_benefits"})

# Extra wages, in dollars, used to measure the marginal tax rate.
MARGINAL_RATE_DELTA = 1_000

# Amounts smaller than this are treated as zero.
CENT = 0.005


def _sum(sim: Simulation, variable: str, year: int) -> float:
    """Calculate a PolicyEngine-US variable and sum it over the household."""
    return float(sim.calculate(variable, year).sum())


def _parameter_list(sim: Simulation, path: str, year: int) -> list[str]:
    """Read a list-valued PolicyEngine-US parameter, such as a program list."""
    node = sim.tax_benefit_system.parameters(f"{year}-01-01")
    for name in path.split("."):
        node = getattr(node, name)
    return list(node)


def _add_nonzero(values: dict[str, float], key: str, value: float) -> None:
    if abs(value) > CENT:
        values[key] = values.get(key, 0.0) + value


def _itemize(
    sim: Simulation,
    programs: list[str],
    total: float,
    year: int,
    remainder_key: str,
) -> dict[str, float]:
    """Itemize an aggregate by program; any unitemized remainder gets its own key.

    The items always sum to ``total``, so the rows reconcile even if
    PolicyEngine-US adds a program this list does not name.
    """
    items: dict[str, float] = {}
    for program in programs:
        _add_nonzero(items, program, _sum(sim, program, year))
    _add_nonzero(items, remainder_key, total - sum(items.values()))
    return items


def _with_extra_wages(household: HouseholdInput, amount: float) -> HouseholdInput:
    """Copy of the household with ``amount`` more wages for the first person."""
    first, *rest = household.people
    raised = first.model_copy(
        update={"employment_income": first.employment_income + amount}
    )
    return household.model_copy(update={"people": [raised, *rest]})


class HouseholdCalculator:
    """Calculate taxes and benefits for a household using PolicyEngine-US."""

    def _build_situation(self, household: HouseholdInput) -> dict:
        """Build a PolicyEngine situation dictionary from HouseholdInput."""
        year = household.year
        state_fips = STATE_FIPS.get(household.state, 6)  # Default to CA

        # Build people
        people = {}
        members = []
        tax_unit_members = []
        head_id = None
        spouse_id = None
        dependents = []

        for i, person in enumerate(household.people):
            person_id = f"person_{i}"
            members.append(person_id)
            tax_unit_members.append(person_id)

            # Track tax unit roles
            if person.is_tax_unit_head:
                head_id = person_id
            elif person.is_tax_unit_spouse:
                spouse_id = person_id
            elif person.is_tax_unit_dependent:
                dependents.append(person_id)

            # Build person data
            person_data = {
                "age": {year: person.age},
            }

            # Income sources
            if person.employment_income > 0:
                person_data["employment_income"] = {year: person.employment_income}
            if person.self_employment_income > 0:
                person_data["self_employment_income"] = {
                    year: person.self_employment_income
                }
            if person.social_security > 0:
                person_data["social_security_retirement"] = {
                    year: person.social_security
                }
            if person.pension_income > 0:
                person_data["taxable_pension_income"] = {year: person.pension_income}
            if person.investment_income > 0:
                person_data["dividend_income"] = {year: person.investment_income}
            if person.capital_gains > 0:
                person_data["long_term_capital_gains"] = {year: person.capital_gains}

            # Tax unit roles
            if person.is_tax_unit_head:
                person_data["is_tax_unit_head"] = {year: True}
            if person.is_tax_unit_spouse:
                person_data["is_tax_unit_spouse"] = {year: True}
            if person.is_tax_unit_dependent:
                person_data["is_tax_unit_dependent"] = {year: True}

            people[person_id] = person_data

        # If no explicit head, set the first adult as head
        if not head_id and members:
            head_id = members[0]
            people[head_id]["is_tax_unit_head"] = {year: True}

        # Build tax unit
        tax_unit = {
            "members": tax_unit_members,
            "filing_status": {
                year: FILING_STATUS_PE_SITUATION.get(household.filing_status, "SINGLE")
            },
        }

        # Build situation
        situation = {
            "people": people,
            "households": {
                "household": {
                    "members": members,
                    "state_fips": {year: state_fips},
                }
            },
            "tax_units": {
                "tax_unit": tax_unit,
            },
            "families": {
                "family": {
                    "members": members,
                }
            },
            "spm_units": {
                "spm_unit": {
                    "members": members,
                }
            },
            "marital_units": {},
        }

        # Build marital units
        if spouse_id and head_id:
            situation["marital_units"]["marital_unit"] = {
                "members": [head_id, spouse_id],
            }
        elif head_id:
            situation["marital_units"]["marital_unit"] = {
                "members": [head_id],
            }

        # Add individual marital units for dependents
        for i, dep_id in enumerate(dependents):
            situation["marital_units"][f"marital_unit_{i}"] = {
                "members": [dep_id],
            }

        return situation

    def calculate(self, household: HouseholdInput) -> HouseholdResult:
        """Calculate taxes, benefits and net income for a household.

        The marginal tax rate is the share of ``MARGINAL_RATE_DELTA`` more
        wages for the first person that does not reach net income, so it
        reflects taxes, refundable credit phase-outs and benefit reductions.
        """
        result = self._calculate_resources(household)
        raised = self._calculate_resources(
            _with_extra_wages(household, MARGINAL_RATE_DELTA)
        )
        marginal_tax_rate = 1 - (raised.net_income - result.net_income) / (
            MARGINAL_RATE_DELTA
        )
        return result.model_copy(update={"marginal_tax_rate": marginal_tax_rate})

    def _calculate_resources(self, household: HouseholdInput) -> HouseholdResult:
        """Taxes, benefits and net income, without the marginal tax rate."""
        year = household.year
        sim = Simulation(situation=self._build_situation(household))

        total_income = sum(
            p.employment_income
            + p.self_employment_income
            + p.social_security
            + p.pension_income
            + p.investment_income
            + p.capital_gains
            for p in household.people
        )

        # Taxes, all before refundable credits.
        federal_income_tax = _sum(sim, "income_tax_before_refundable_credits", year)
        state_income_tax = _sum(sim, "state_income_tax_before_refundable_credits", year)
        state_payroll_tax = _sum(sim, "employee_state_payroll_tax", year)
        self_employment_tax = _sum(sim, "self_employment_tax", year)
        payroll_tax = _sum(sim, "employee_payroll_tax", year) + self_employment_tax
        total_taxes = _sum(sim, "household_tax_before_refundable_credits", year)
        other_taxes = total_taxes - federal_income_tax - state_income_tax - payroll_tax

        tax_breakdown = {
            "federal_income_tax": federal_income_tax,
            "state_income_tax": state_income_tax,
            "fica": payroll_tax - state_payroll_tax - self_employment_tax,
            "state_payroll_tax": state_payroll_tax,
            "self_employment_tax": self_employment_tax,
        }
        tax_breakdown.update(
            _itemize(
                sim,
                [
                    "state_use_tax",
                    "local_income_tax_before_refundable_credits",
                    "local_occupational_tax",
                ],
                other_taxes,
                year,
                remainder_key="other_taxes",
            )
        )

        # Benefits: PolicyEngine's household benefits, less Social Security and
        # health coverage, plus refundable credits. Each item appears once.
        non_credit_benefits = (
            _sum(sim, "household_benefits", year)
            - _sum(sim, "social_security", year)
            - _sum(sim, "household_health_benefits", year)
        )
        federal_refundable_credits = _sum(sim, "income_tax_refundable_credits", year)
        state_refundable_credits = _sum(
            sim, "household_refundable_state_tax_credits", year
        )
        refundable_tax_credits = federal_refundable_credits + state_refundable_credits

        benefits = _itemize(
            sim,
            [
                program
                for program in _parameter_list(
                    sim, "gov.household.household_benefits", year
                )
                if program not in EXCLUDED_BENEFITS
            ],
            non_credit_benefits,
            year,
            remainder_key="other_benefits",
        )
        # Market income PolicyEngine computes beyond what the user entered,
        # such as the Alaska Permanent Fund Dividend. PolicyEngine counts it as
        # market income; EggNest shows it as its own line so total_income stays
        # what the user typed.
        entered_market_income = total_income - sum(
            p.social_security for p in household.people
        )
        benefits.update(
            _itemize(
                sim,
                ["ak_permanent_fund_dividend"],
                _sum(sim, "household_market_income", year) - entered_market_income,
                year,
                remainder_key="other_computed_income",
            )
        )
        benefits.update(
            _itemize(
                sim,
                _parameter_list(sim, "gov.irs.credits.refundable", year),
                federal_refundable_credits,
                year,
                remainder_key="other_federal_refundable_credits",
            )
        )
        _add_nonzero(
            benefits, "household_refundable_state_tax_credits", state_refundable_credits
        )
        total_benefits = sum(benefits.values())

        net_income = total_income - total_taxes + total_benefits
        effective_tax_rate = total_taxes / total_income if total_income > 0 else 0

        return HouseholdResult(
            federal_income_tax=federal_income_tax,
            state_income_tax=state_income_tax,
            payroll_tax=payroll_tax,
            other_taxes=other_taxes,
            total_taxes=total_taxes,
            benefits=benefits,
            total_benefits=total_benefits,
            refundable_tax_credits=refundable_tax_credits,
            non_refundable_tax_credits=_sum(
                sim, "income_tax_capped_non_refundable_credits", year
            ),
            total_income=total_income,
            net_income=net_income,
            tax_breakdown=tax_breakdown,
            effective_tax_rate=effective_tax_rate,
        )

    def compare(
        self,
        before: HouseholdInput,
        after: HouseholdInput,
        event_name: str = "Life Event",
    ) -> LifeEventComparison:
        """Compare tax outcomes before and after a life event."""
        before_result = self.calculate(before)
        after_result = self.calculate(after)

        tax_change = after_result.total_taxes - before_result.total_taxes
        benefit_change = after_result.total_benefits - before_result.total_benefits
        net_income_change = after_result.net_income - before_result.net_income

        return LifeEventComparison(
            event_name=event_name,
            before_result=before_result,
            after_result=after_result,
            tax_change=tax_change,
            benefit_change=benefit_change,
            net_income_change=net_income_change,
        )
