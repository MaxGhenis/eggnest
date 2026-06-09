"""Household tax and benefits calculator using PolicyEngine-US."""

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


def _calculate_sum(sim: Simulation, variable: str, year: int) -> float:
    """Calculate a PolicyEngine variable and return its household/tax-unit sum."""
    return float(sim.calculate(variable, year).sum())


def _calculate_sum_or_zero(sim: Simulation, variable: str, year: int) -> float:
    """Return 0 when a PolicyEngine variable is not available in this version."""
    try:
        return _calculate_sum(sim, variable, year)
    except Exception:
        return 0.0


def _add_positive(values: dict[str, float], key: str, value: float) -> None:
    if value > 0:
        values[key] = value


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
        """Calculate taxes and benefits for a household."""
        year = household.year
        situation = self._build_situation(household)

        # Run simulation
        sim = Simulation(situation=situation)

        # Calculate total income
        total_income = sum(
            p.employment_income
            + p.self_employment_income
            + p.social_security
            + p.pension_income
            + p.investment_income
            + p.capital_gains
            for p in household.people
        )

        # Get tax results. Federal income_tax is net of refundable credits in
        # PolicyEngine-US, so use the pre-refundable liability and count
        # refundable credits in benefits to avoid double-counting cash resources.
        federal_income_tax = _calculate_sum(
            sim, "income_tax_before_refundable_credits", year
        )
        federal_income_tax_after_refundable_credits = _calculate_sum(
            sim, "income_tax", year
        )
        state_income_tax = _calculate_sum(sim, "state_income_tax", year)

        # Calculate payroll taxes (employee side)
        employee_social_security_tax = _calculate_sum(
            sim, "employee_social_security_tax", year
        )
        employee_medicare_tax = _calculate_sum(sim, "employee_medicare_tax", year)
        payroll_tax = employee_social_security_tax + employee_medicare_tax

        # Self-employment tax if applicable
        self_employment_tax = _calculate_sum_or_zero(sim, "self_employment_tax", year)
        payroll_tax += self_employment_tax

        total_taxes = federal_income_tax + state_income_tax + payroll_tax

        # Get cash-equivalent benefits and refundable credits.
        benefits = {}

        refundable_ctc = _calculate_sum_or_zero(sim, "refundable_ctc", year)
        eitc = _calculate_sum_or_zero(sim, "eitc", year)
        refundable_credit_total = _calculate_sum_or_zero(
            sim, "income_tax_refundable_credits", year
        )
        remaining_refundable_credits = refundable_credit_total

        _add_positive(benefits, "child_tax_credit", refundable_ctc)
        remaining_refundable_credits -= refundable_ctc
        _add_positive(benefits, "eitc", eitc)
        remaining_refundable_credits -= eitc

        cdcc = _calculate_sum_or_zero(sim, "cdcc", year)
        if cdcc > 0 and remaining_refundable_credits >= cdcc - 0.01:
            benefits["child_care_credit"] = cdcc
            remaining_refundable_credits -= cdcc

        # SNAP
        snap = _calculate_sum_or_zero(sim, "snap", year)
        _add_positive(benefits, "snap", snap)

        if remaining_refundable_credits > 0.01:
            benefits["other_refundable_tax_credits"] = remaining_refundable_credits

        total_benefits = sum(benefits.values())

        # Calculate net income
        net_income = total_income - total_taxes + total_benefits

        # Tax breakdown
        tax_breakdown = {
            "federal_income_tax": federal_income_tax,
            "federal_income_tax_after_refundable_credits": (
                federal_income_tax_after_refundable_credits
            ),
            "federal_refundable_tax_credits": refundable_credit_total,
            "federal_non_refundable_tax_credits_used": _calculate_sum_or_zero(
                sim, "income_tax_capped_non_refundable_credits", year
            ),
            "child_tax_credit_total": _calculate_sum_or_zero(sim, "ctc", year),
            "child_tax_credit_refundable": refundable_ctc,
            "child_care_credit_total": cdcc,
            "state_income_tax": state_income_tax,
            "self_employment_tax": self_employment_tax,
            "fica": employee_social_security_tax + employee_medicare_tax,
        }

        # Calculate marginal tax rate (add $1000 and see tax change)
        if total_income > 0:
            marginal_situation = self._build_situation(household)
            # Add $1000 to first person's employment income
            first_person = list(marginal_situation["people"].keys())[0]
            current_income = (
                marginal_situation["people"][first_person]
                .get("employment_income", {})
                .get(year, 0)
            )
            marginal_situation["people"][first_person]["employment_income"] = {
                year: current_income + 1000
            }

            marginal_sim = Simulation(situation=marginal_situation)
            marginal_federal = _calculate_sum(
                marginal_sim, "income_tax_before_refundable_credits", year
            )
            marginal_state = _calculate_sum(marginal_sim, "state_income_tax", year)
            marginal_payroll = _calculate_sum(
                marginal_sim, "employee_social_security_tax", year
            )
            marginal_payroll += _calculate_sum(
                marginal_sim, "employee_medicare_tax", year
            )

            marginal_total = marginal_federal + marginal_state + marginal_payroll
            base_total = federal_income_tax + state_income_tax + payroll_tax
            marginal_tax_rate = (marginal_total - base_total) / 1000
        else:
            marginal_tax_rate = 0

        # Effective tax rate
        effective_tax_rate = total_taxes / total_income if total_income > 0 else 0

        result = HouseholdResult(
            federal_income_tax=federal_income_tax,
            state_income_tax=state_income_tax,
            payroll_tax=payroll_tax,
            total_taxes=total_taxes,
            benefits=benefits,
            total_benefits=total_benefits,
            total_income=total_income,
            net_income=net_income,
            tax_breakdown=tax_breakdown,
            marginal_tax_rate=marginal_tax_rate,
            effective_tax_rate=effective_tax_rate,
        )
        return result.model_copy(
            update={
                "citations": household_resource_citations(result),
                "output_citations": household_resource_output_citations(result),
            }
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
    previous_result: HouseholdResult | None = None
    previous_income: float | None = None
    cliffs: list[EarningsGridCliff] = []

    for income in incomes:
        household = _with_person_employment_income(
            grid_input.base_input,
            grid_input.person_index,
            income,
        )
        result = calc.calculate(household)

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
        previous_result = result
        previous_income = income

    largest_cliff = min(cliffs, key=lambda cliff: cliff.net_income_change, default=None)

    citation_context = SimpleNamespace(
        benefits={
            benefit_key: 1
            for row in rows
            for benefit_key in row.benefits
            if row.benefits[benefit_key] > 0
        },
        tax_breakdown={},
        payroll_tax=0,
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
