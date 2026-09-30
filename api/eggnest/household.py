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
Non-refundable credits are already inside ``federal_income_tax``; they are
itemized in ``non_refundable_credit_breakdown`` for reference only.
"""

from types import SimpleNamespace

from policyengine_us import Simulation
from pydantic import ValidationError

from eggnest.citations import (
    household_resource_citations,
    household_resource_output_citations,
)
from eggnest.constants import FILING_STATUS_PE_SITUATION, STATE_FIPS
from eggnest.models import (
    EarningsGridCliff,
    EarningsGridComparisonResult,
    EarningsGridInput,
    EarningsGridPoint,
    HouseholdInput,
    HouseholdResult,
    HouseholdValidationResult,
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


def primary_earner_index(household: HouseholdInput) -> int:
    """Index of the person whose earnings carry the marginal $1,000.

    Picks the non-dependent person with the highest earned income, falling
    back to the tax-unit head, so a child listed first does not become the
    marginal earner.
    """
    candidates = [
        (i, person)
        for i, person in enumerate(household.people)
        if not person.is_tax_unit_dependent
    ]
    if not candidates:
        return 0
    return max(
        candidates,
        key=lambda item: (
            item[1].employment_income + item[1].self_employment_income,
            item[1].is_tax_unit_head,
        ),
    )[0]


def _with_extra_wages(household: HouseholdInput, amount: float) -> HouseholdInput:
    """Copy of the household with ``amount`` more wages for the primary earner."""
    index = primary_earner_index(household)
    people = list(household.people)
    earner = people[index]
    people[index] = earner.model_copy(
        update={"employment_income": earner.employment_income + amount}
    )
    return household.model_copy(update={"people": people})


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
        wages for the primary earner that does not reach net income, so it
        reflects taxes, refundable credit phase-outs and benefit reductions.
        """
        result = self._calculate_resources(household)
        raised = self._calculate_resources(
            _with_extra_wages(household, MARGINAL_RATE_DELTA)
        )
        marginal_tax_rate = 1 - (raised.net_income - result.net_income) / (
            MARGINAL_RATE_DELTA
        )
        return result.model_copy(
            update={
                "marginal_tax_rate": marginal_tax_rate,
                "citations": household_resource_citations(result),
                "output_citations": household_resource_output_citations(result),
            }
        )

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
                    # Zero under current law; a PolicyEngine-US reform can add it.
                    "flat_tax",
                ],
                other_taxes,
                year,
                remainder_key="other_taxes",
            )
        )

        # Non-refundable credits are already subtracted in federal_income_tax.
        # Itemize the ones PolicyEngine counts; the part that exceeds the tax
        # they can offset is a negative remainder, so the items sum to the
        # credits actually used.
        non_refundable_tax_credits = _sum(
            sim, "income_tax_capped_non_refundable_credits", year
        )
        non_refundable_credit_breakdown = _itemize(
            sim,
            _parameter_list(sim, "gov.irs.credits.non_refundable", year),
            non_refundable_tax_credits,
            year,
            remainder_key="unavailable_non_refundable_credits",
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
            non_refundable_tax_credits=non_refundable_tax_credits,
            non_refundable_credit_breakdown=non_refundable_credit_breakdown,
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


INCOME_FIELDS = {
    "employment_income",
    "self_employment_income",
    "social_security",
    "pension_income",
    "investment_income",
    "capital_gains",
}


def validate_household_payload(data: dict) -> HouseholdValidationResult:
    """Validate partial household intake and tell agents what to ask next."""
    missing_inputs: list[str] = []
    high_impact_questions: list[str] = []
    safe_defaults_used: dict[str, object] = {}
    errors: list[str] = []

    if "state" not in data:
        missing_inputs.append("state")
        high_impact_questions.append("What state does the household live in?")
    if "year" not in data:
        safe_defaults_used["year"] = HouseholdInput.model_fields["year"].default
    if "filing_status" not in data:
        safe_defaults_used["filing_status"] = HouseholdInput.model_fields[
            "filing_status"
        ].default

    people = data.get("people")
    if not isinstance(people, list) or not people:
        missing_inputs.append("people")
        high_impact_questions.append(
            "Who is in the household, and what are their ages?"
        )
    else:
        for index, person in enumerate(people):
            if not isinstance(person, dict):
                errors.append(f"people[{index}] must be an object")
                continue
            if "age" not in person:
                missing_inputs.append(f"people[{index}].age")
            if not any(field in person for field in INCOME_FIELDS):
                missing_inputs.append(f"people[{index}].income")
                high_impact_questions.append(
                    f"What annual income sources does person {index} have?"
                )

    if errors:
        return HouseholdValidationResult(
            status="invalid",
            missing_inputs=missing_inputs,
            high_impact_questions=_dedupe(high_impact_questions),
            safe_defaults_used=safe_defaults_used,
            errors=errors,
        )

    if missing_inputs:
        return HouseholdValidationResult(
            status="needs_input",
            missing_inputs=_dedupe(missing_inputs),
            high_impact_questions=_dedupe(high_impact_questions),
            safe_defaults_used=safe_defaults_used,
        )

    try:
        HouseholdInput.model_validate(data)
    except ValidationError as exc:
        return HouseholdValidationResult(
            status="invalid",
            safe_defaults_used=safe_defaults_used,
            errors=[
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            ],
        )

    return HouseholdValidationResult(
        status="ready",
        safe_defaults_used=safe_defaults_used,
    )


def compare_earnings_grid(
    grid_input: EarningsGridInput,
) -> EarningsGridComparisonResult:
    """Compare household resources across earned-income levels.

    Policy calculations remain delegated to PolicyEngine-US via
    ``HouseholdCalculator``. This function only orchestrates scenario copies and
    summarizes the resource curve for agents.
    """
    calc = HouseholdCalculator()
    incomes = _grid_values(
        grid_input.income_min,
        grid_input.income_max,
        grid_input.step,
    )

    rows: list[EarningsGridPoint] = []
    results: list[HouseholdResult] = []
    previous_result: HouseholdResult | None = None
    previous_income: float | None = None
    cliffs: list[EarningsGridCliff] = []

    for income in incomes:
        household = _with_person_employment_income(
            grid_input.base_input,
            grid_input.person_index,
            income,
        )
        # Rows need net resources, not the per-row marginal tax rate, so skip
        # the extra +$1,000 simulation that calculate() runs.
        result = calc._calculate_resources(household)

        delta_net_income = None
        effective_marginal_rate = None
        if previous_result is not None and previous_income is not None:
            income_change = income - previous_income
            net_change = result.net_income - previous_result.net_income
            if income_change > 0:
                delta_net_income = net_change
                effective_marginal_rate = 1 - (net_change / income_change)
                if net_change < 0:
                    benefit_changes = _dict_delta(
                        result.benefits,
                        previous_result.benefits,
                    )
                    cliffs.append(
                        EarningsGridCliff(
                            from_income=previous_income,
                            to_income=income,
                            net_income_change=net_change,
                            tax_change=result.total_taxes - previous_result.total_taxes,
                            benefit_change=result.total_benefits
                            - previous_result.total_benefits,
                            effective_marginal_rate=effective_marginal_rate,
                            benefit_changes=benefit_changes,
                        )
                    )

        rows.append(
            EarningsGridPoint(
                employment_income=income,
                total_income=result.total_income,
                net_income=result.net_income,
                total_taxes=result.total_taxes,
                total_benefits=result.total_benefits,
                benefits=result.benefits,
                delta_net_income=delta_net_income,
                effective_marginal_rate=effective_marginal_rate,
            )
        )
        results.append(result)
        previous_result = result
        previous_income = income

    largest_cliff = min(cliffs, key=lambda cliff: cliff.net_income_change, default=None)

    # Cite every source any row relies on: each benefit, credit and tax that
    # is non-zero somewhere on the grid.
    citation_context = SimpleNamespace(
        benefits=_union_of_nonzero(result.benefits for result in results),
        tax_breakdown=_union_of_nonzero(result.tax_breakdown for result in results),
        non_refundable_credit_breakdown=_union_of_nonzero(
            result.non_refundable_credit_breakdown for result in results
        ),
    )

    return EarningsGridComparisonResult(
        person_index=grid_input.person_index,
        income_min=grid_input.income_min,
        income_max=grid_input.income_max,
        step=grid_input.step,
        rows=rows,
        cliffs=cliffs,
        largest_cliff=largest_cliff,
        comparison_summary=_earnings_grid_summary(rows, cliffs),
        citations=household_resource_citations(citation_context),
        output_citations=household_resource_output_citations(citation_context),
    )


def _with_person_employment_income(
    household: HouseholdInput,
    person_index: int,
    employment_income: float,
) -> HouseholdInput:
    people = [person.model_copy() for person in household.people]
    people[person_index] = people[person_index].model_copy(
        update={"employment_income": employment_income}
    )
    return household.model_copy(update={"people": people})


def _grid_values(income_min: float, income_max: float, step: float) -> list[float]:
    values = []
    current = income_min
    while current <= income_max + 1e-9:
        values.append(round(current, 2))
        current += step
    if values[-1] != income_max:
        values.append(round(income_max, 2))
    return values


def _union_of_nonzero(dicts) -> dict[str, float]:
    """Largest absolute value of each key that is non-zero in any dict."""
    union: dict[str, float] = {}
    for values in dicts:
        for key, value in values.items():
            if value != 0:
                union[key] = max(union.get(key, 0.0), abs(value))
    return union


def _dict_delta(
    current: dict[str, float],
    previous: dict[str, float],
) -> dict[str, float]:
    keys = set(current) | set(previous)
    return {
        key: current.get(key, 0.0) - previous.get(key, 0.0)
        for key in sorted(keys)
        if current.get(key, 0.0) != previous.get(key, 0.0)
    }


def _earnings_grid_summary(
    rows: list[EarningsGridPoint],
    cliffs: list[EarningsGridCliff],
) -> str:
    if not rows:
        return "No earnings grid rows were evaluated."
    best = max(rows, key=lambda row: row.net_income)
    if cliffs:
        largest = min(cliffs, key=lambda cliff: cliff.net_income_change)
        return (
            f"Evaluated {len(rows)} earnings levels. Net resources are highest at "
            f"${best.employment_income:,.0f} of annual earnings. The largest modeled "
            f"cliff is ${largest.net_income_change:,.0f} between "
            f"${largest.from_income:,.0f} and ${largest.to_income:,.0f}."
        )
    return (
        f"Evaluated {len(rows)} earnings levels. Net resources are highest at "
        f"${best.employment_income:,.0f} of annual earnings; no negative net-resource "
        "steps appear on this grid."
    )


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
