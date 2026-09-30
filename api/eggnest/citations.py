"""Citation helpers for agent-facing calculation outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Citation(BaseModel):
    """FinBot-compatible source link shape."""

    id: str
    url: str
    title: str | None = None
    source: str | None = None


POLICYENGINE_US_URL = "https://github.com/PolicyEngine/policyengine-us"


def _axiom_us_url(kind: str, *parts: str) -> str:
    return f"https://axiom.org/us/{kind}/{'/'.join(parts)}"


def _statute(usc_title: str, section: str, title: str) -> Citation:
    return Citation(
        id=f"us:statutes/{usc_title}/{section}",
        url=_axiom_us_url("statute", usc_title, section),
        title=title,
        source=f"{usc_title} USC {section}",
    )


def _policyengine_variable(variable: str, title: str | None = None) -> Citation:
    return Citation(
        id=f"policyengine-us:variables/{variable}",
        url=POLICYENGINE_US_URL,
        title=title or variable,
        source="PolicyEngine-US variable",
    )


_CHILD_TAX_CREDIT = _statute("26", "24", "Child Tax Credit")
_EDUCATION_CREDITS = _statute(
    "26", "25A", "American Opportunity and Lifetime Learning credits"
)

# Sources keyed by HouseholdResult field or by the PolicyEngine-US variable
# names used as keys in ``benefits``, ``tax_breakdown`` and
# ``non_refundable_credit_breakdown``. Statutes are cited where the federal
# statute sets the amount; other keys cite the PolicyEngine-US variable that
# computes them.
HOUSEHOLD_CITATIONS = {
    # Taxes
    "federal_income_tax": _policyengine_variable(
        "income_tax_before_refundable_credits",
        "Federal income tax before refundable credits",
    ),
    "state_income_tax": _policyengine_variable(
        "state_income_tax_before_refundable_credits",
        "State income tax before refundable credits",
    ),
    "payroll_tax": _statute("26", "3101", "Employee FICA tax"),
    "self_employment_tax": _statute("26", "1401", "Self-employment tax"),
    "state_payroll_tax": _policyengine_variable(
        "employee_state_payroll_tax", "Employee state payroll taxes"
    ),
    "state_use_tax": _policyengine_variable("state_use_tax", "State use tax"),
    "local_income_tax_before_refundable_credits": _policyengine_variable(
        "local_income_tax_before_refundable_credits",
        "Local income tax before refundable credits",
    ),
    "local_occupational_tax": _policyengine_variable(
        "local_occupational_tax", "Local occupational tax"
    ),
    "other_taxes": _policyengine_variable(
        "household_tax_before_refundable_credits",
        "Total tax before refundable credits",
    ),
    # Federal tax credits
    "refundable_ctc": _CHILD_TAX_CREDIT,
    "non_refundable_ctc": _CHILD_TAX_CREDIT,
    "eitc": _statute("26", "32", "Earned Income Tax Credit"),
    "cdcc": _statute("26", "21", "Child and dependent care credit"),
    "refundable_american_opportunity_credit": _EDUCATION_CREDITS,
    "non_refundable_american_opportunity_credit": _EDUCATION_CREDITS,
    "lifetime_learning_credit": _EDUCATION_CREDITS,
    "savers_credit": _statute("26", "25B", "Saver's credit"),
    "elderly_disabled_credit": _statute(
        "26", "22", "Credit for the elderly and the permanently and totally disabled"
    ),
    "foreign_tax_credit": _statute("26", "27", "Foreign tax credit"),
    "residential_clean_energy_credit": _statute(
        "26", "25D", "Residential clean energy credit"
    ),
    "energy_efficient_home_improvement_credit": _statute(
        "26", "25C", "Energy efficient home improvement credit"
    ),
    "new_clean_vehicle_credit": _statute("26", "30D", "Clean vehicle credit"),
    "used_clean_vehicle_credit": _statute(
        "26", "25E", "Previously-owned clean vehicle credit"
    ),
    "recovery_rebate_credit": _policyengine_variable(
        "recovery_rebate_credit", "Recovery rebate credit"
    ),
    "refundable_payroll_tax_credit": _policyengine_variable(
        "refundable_payroll_tax_credit", "Refundable payroll tax credit"
    ),
    "other_federal_refundable_credits": _policyengine_variable(
        "income_tax_refundable_credits", "Federal refundable income tax credits"
    ),
    "unavailable_non_refundable_credits": _policyengine_variable(
        "income_tax_unavailable_non_refundable_credits",
        "Non-refundable credits that exceed the tax they can offset",
    ),
    "household_refundable_state_tax_credits": _policyengine_variable(
        "household_refundable_state_tax_credits", "State refundable tax credits"
    ),
    # Benefit programs
    "snap": _statute("7", "2017", "SNAP allotment"),
    "ssi": _statute("42", "1382", "Supplemental Security Income"),
    "wic": _statute(
        "42",
        "1786",
        "Special Supplemental Nutrition Program for Women, Infants, and Children",
    ),
    "tanf": _policyengine_variable("tanf", "TANF"),
    "free_school_meals": _policyengine_variable(
        "free_school_meals", "Free school meals"
    ),
    "reduced_price_school_meals": _policyengine_variable(
        "reduced_price_school_meals", "Reduced-price school meals"
    ),
    "commodity_supplemental_food_program": _policyengine_variable(
        "commodity_supplemental_food_program", "Commodity Supplemental Food Program"
    ),
    "household_state_benefits": _policyengine_variable(
        "household_state_benefits", "State benefits"
    ),
    "housing_assistance": _policyengine_variable(
        "housing_assistance", "Housing assistance"
    ),
    "household_head_start_benefits": _policyengine_variable(
        "household_head_start_benefits", "Head Start"
    ),
    "unemployment_compensation": _policyengine_variable(
        "unemployment_compensation", "Unemployment compensation"
    ),
    "ak_permanent_fund_dividend": _policyengine_variable(
        "ak_permanent_fund_dividend", "Alaska Permanent Fund Dividend"
    ),
    "other_benefits": _policyengine_variable(
        "household_benefits", "Household benefits"
    ),
    "other_computed_income": _policyengine_variable(
        "household_market_income", "Household market income"
    ),
}

# Taxes cited for every household, whatever their amount.
TAX_CITATION_KEYS = (
    "federal_income_tax",
    "state_income_tax",
    "payroll_tax",
)

# tax_breakdown keys that make up other_taxes.
OTHER_TAX_KEYS = (
    "state_use_tax",
    "local_income_tax_before_refundable_credits",
    "local_occupational_tax",
    "flat_tax",
    "other_taxes",
)

# Keys cited when no result is given (the catalog of the main sources).
DEFAULT_BENEFIT_KEYS = ("eitc", "refundable_ctc", "snap", "ssi")
DEFAULT_NON_REFUNDABLE_CREDIT_KEYS = ("non_refundable_ctc", "cdcc")


def household_resource_citations(result: Any | None = None) -> list[Citation]:
    """Return a flat, deduplicated source list for a household resource result."""
    return _dedupe_citations(
        citation
        for citations in household_resource_output_citations(result).values()
        for citation in citations
    )


def household_resource_output_citations(
    result: Any | None = None,
) -> dict[str, list[Citation]]:
    """Map household result fields to the sources that support them.

    Every key in ``benefits`` and ``non_refundable_credit_breakdown`` gets an
    entry (``benefits.<key>``, ``non_refundable_credit_breakdown.<key>``);
    keys without a mapped source cite the PolicyEngine-US variable of that name.
    """
    benefit_keys = _benefit_keys(result)
    credit_keys = _non_refundable_credit_keys(result)

    federal_citations = _citations_for_keys(["federal_income_tax", *credit_keys])
    state_citations = _citations_for_keys(["state_income_tax"])
    payroll_citations = _citations_for_keys(_payroll_keys(result))
    other_tax_citations = _citations_for_keys(_other_tax_keys(result))
    tax_citations = _dedupe_citations(
        [
            *federal_citations,
            *state_citations,
            *payroll_citations,
            *other_tax_citations,
        ]
    )
    benefit_citations = _citations_for_keys(benefit_keys)
    resource_citations = _dedupe_citations([*tax_citations, *benefit_citations])

    output_citations: dict[str, list[Citation]] = {
        "federal_income_tax": federal_citations,
        "state_income_tax": state_citations,
        "payroll_tax": payroll_citations,
        "other_taxes": other_tax_citations,
        "total_taxes": tax_citations,
        "total_benefits": benefit_citations,
        "non_refundable_tax_credits": _citations_for_keys(credit_keys),
        "net_income": resource_citations,
        "effective_tax_rate": tax_citations,
        # The marginal rate counts benefit and credit phase-outs as well as taxes.
        "marginal_tax_rate": resource_citations,
    }

    for benefit_key in benefit_keys:
        output_citations[f"benefits.{benefit_key}"] = _citations_for_keys([benefit_key])
    for credit_key in credit_keys:
        output_citations[f"non_refundable_credit_breakdown.{credit_key}"] = (
            _citations_for_keys([credit_key])
        )

    return {key: value for key, value in output_citations.items() if value}


def _benefit_keys(result: Any | None) -> list[str]:
    if result is None:
        return list(DEFAULT_BENEFIT_KEYS)
    benefits = getattr(result, "benefits", {}) or {}
    return sorted(benefits)


def _non_refundable_credit_keys(result: Any | None) -> list[str]:
    if result is None:
        return list(DEFAULT_NON_REFUNDABLE_CREDIT_KEYS)
    breakdown = getattr(result, "non_refundable_credit_breakdown", {}) or {}
    return sorted(breakdown)


def _payroll_keys(result: Any | None) -> list[str]:
    keys = ["payroll_tax"]
    if result is None:
        return [*keys, "self_employment_tax"]
    tax_breakdown = getattr(result, "tax_breakdown", {}) or {}
    if tax_breakdown.get("self_employment_tax", 0) > 0:
        keys.append("self_employment_tax")
    if tax_breakdown.get("state_payroll_tax", 0) > 0:
        keys.append("state_payroll_tax")
    return keys


def _other_tax_keys(result: Any | None) -> list[str]:
    if result is None:
        return []
    tax_breakdown = getattr(result, "tax_breakdown", {}) or {}
    return [key for key in OTHER_TAX_KEYS if tax_breakdown.get(key, 0) != 0]


def _citation_for_key(key: str) -> Citation:
    return HOUSEHOLD_CITATIONS.get(key) or _policyengine_variable(key)


def _citations_for_keys(keys: list[str] | tuple[str, ...]) -> list[Citation]:
    return _dedupe_citations(_citation_for_key(key) for key in keys)


def _dedupe_citations(citations: Any) -> list[Citation]:
    seen: set[str] = set()
    deduped: list[Citation] = []
    for citation in citations:
        if citation.id in seen:
            continue
        seen.add(citation.id)
        deduped.append(citation)
    return deduped
