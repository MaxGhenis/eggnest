"""Household tax and benefits calculator using PolicyEngine-US."""

from functools import lru_cache

from policyengine_us import CountryTaxBenefitSystem, Simulation

from eggnest.constants import FILING_STATUS_PE_SITUATION, STATE_FIPS
from eggnest.models import (
    HouseholdInput,
    HouseholdResult,
    LifeEventComparison,
)


@lru_cache(maxsize=1)
def _uses_tax_only_roth_conversions() -> bool:
    """Check whether the installed PolicyEngine-US supports tax-only Roth inputs."""
    try:
        variable = CountryTaxBenefitSystem().get_variable("taxable_roth_conversions")
    except Exception:
        return False
    return variable is not None


def _roth_conversion_variable_name() -> str:
    """Return the best available PolicyEngine input for Roth conversion tax effects."""
    if _uses_tax_only_roth_conversions():
        return "taxable_roth_conversions"
    return "taxable_ira_distributions"


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
        asset_holders = []

        for i, person in enumerate(household.people):
            person_id = f"person_{i}"
            members.append(person_id)
            tax_unit_members.append(person_id)

            # Track tax unit roles
            if person.is_tax_unit_head:
                head_id = person_id
                asset_holders.append(person_id)
            elif person.is_tax_unit_spouse:
                spouse_id = person_id
                asset_holders.append(person_id)
            elif person.is_tax_unit_dependent:
                dependents.append(person_id)
            elif person.age >= 18:
                asset_holders.append(person_id)

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
            if person.roth_conversion_amount > 0:
                person_data[_roth_conversion_variable_name()] = {
                    year: person.roth_conversion_amount
                }

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
            if head_id not in asset_holders:
                asset_holders.append(head_id)

        if household.countable_cash_assets > 0:
            if not asset_holders:
                asset_holders = members[:1]
            per_person_assets = household.countable_cash_assets / len(asset_holders)
            for person_id in asset_holders:
                people[person_id]["bank_account_assets"] = {year: per_person_assets}

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
        modeled_non_cash_income = sum(p.roth_conversion_amount for p in household.people)
        total_modeled_income = total_income + modeled_non_cash_income

        # Get tax results
        federal_income_tax = float(sim.calculate("income_tax", year).sum())
        state_income_tax = float(sim.calculate("state_income_tax", year).sum())

        # Calculate payroll taxes (employee side)
        employee_social_security_tax = float(
            sim.calculate("employee_social_security_tax", year).sum()
        )
        employee_medicare_tax = float(
            sim.calculate("employee_medicare_tax", year).sum()
        )
        payroll_tax = employee_social_security_tax + employee_medicare_tax

        # Self-employment tax if applicable
        try:
            self_employment_tax = float(
                sim.calculate("self_employment_tax", year).sum()
            )
            payroll_tax += self_employment_tax
        except Exception:
            pass

        total_taxes = federal_income_tax + state_income_tax + payroll_tax

        # Get benefits
        benefits = {}

        # Child Tax Credit
        try:
            ctc = float(sim.calculate("ctc", year).sum())
            if ctc > 0:
                benefits["child_tax_credit"] = ctc
        except Exception:
            pass

        # EITC
        try:
            eitc = float(sim.calculate("eitc", year).sum())
            if eitc > 0:
                benefits["eitc"] = eitc
        except Exception:
            pass

        # SNAP
        try:
            snap = float(sim.calculate("snap", year).sum())
            if snap > 0:
                benefits["snap"] = snap
        except Exception:
            pass

        # SSI
        try:
            ssi = float(sim.calculate("ssi", year).sum())
            if ssi > 0:
                benefits["ssi"] = ssi
        except Exception:
            pass

        # Other credits
        try:
            cdcc = float(sim.calculate("cdcc", year).sum())
            if cdcc > 0:
                benefits["child_care_credit"] = cdcc
        except Exception:
            pass

        total_benefits = sum(benefits.values())

        # Calculate net income
        net_income = total_income - total_taxes + total_benefits

        # Tax breakdown
        tax_breakdown = {
            "federal_income_tax": federal_income_tax,
            "state_income_tax": state_income_tax,
            "fica": payroll_tax,
        }

        # Calculate marginal tax rate (add $1000 and see tax change)
        if total_modeled_income > 0:
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
            marginal_federal = float(marginal_sim.calculate("income_tax", year).sum())
            marginal_state = float(
                marginal_sim.calculate("state_income_tax", year).sum()
            )
            marginal_payroll = float(
                marginal_sim.calculate("employee_social_security_tax", year).sum()
            )
            marginal_payroll += float(
                marginal_sim.calculate("employee_medicare_tax", year).sum()
            )

            marginal_total = marginal_federal + marginal_state + marginal_payroll
            base_total = federal_income_tax + state_income_tax + payroll_tax
            marginal_tax_rate = (marginal_total - base_total) / 1000
        else:
            marginal_tax_rate = 0

        # Effective tax rate
        effective_tax_rate = (
            total_taxes / total_modeled_income if total_modeled_income > 0 else 0
        )

        return HouseholdResult(
            federal_income_tax=federal_income_tax,
            state_income_tax=state_income_tax,
            payroll_tax=payroll_tax,
            total_taxes=total_taxes,
            benefits=benefits,
            total_benefits=total_benefits,
            total_income=total_income,
            modeled_non_cash_income=modeled_non_cash_income,
            total_modeled_income=total_modeled_income,
            net_income=net_income,
            tax_breakdown=tax_breakdown,
            marginal_tax_rate=marginal_tax_rate,
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
