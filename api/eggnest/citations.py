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


def _axiom_us_url(kind: str, *parts: str) -> str:
    return f"https://app.axiom-foundation.org/us/{kind}/{'/'.join(parts)}"


HOUSEHOLD_CITATIONS = {
    "federal_income_tax": Citation(
        id="policyengine-us:variables/income_tax_before_refundable_credits",
        url="https://github.com/PolicyEngine/policyengine-us",
        title="Federal income tax before refundable credits",
        source="PolicyEngine-US variable",
    ),
    "state_income_tax": Citation(
        id="policyengine-us:variables/state_income_tax",
        url="https://github.com/PolicyEngine/policyengine-us",
        title="State income tax",
        source="PolicyEngine-US variable",
    ),
    "payroll_tax": Citation(
        id="us:statutes/26/3101",
        url=_axiom_us_url("statute", "26", "3101"),
        title="Employee FICA tax",
        source="26 USC 3101",
    ),
    "self_employment_tax": Citation(
        id="us:statutes/26/1401",
        url=_axiom_us_url("statute", "26", "1401"),
        title="Self-employment tax",
        source="26 USC 1401",
    ),
    "child_tax_credit": Citation(
        id="us:statutes/26/24",
        url=_axiom_us_url("statute", "26", "24"),
        title="Child Tax Credit",
        source="26 USC 24",
    ),
    "eitc": Citation(
        id="us:statutes/26/32",
        url=_axiom_us_url("statute", "26", "32"),
        title="Earned Income Tax Credit",
        source="26 USC 32",
    ),
    "snap": Citation(
        id="us:statutes/7/2017",
        url=_axiom_us_url("statute", "7", "2017"),
        title="SNAP allotment",
        source="7 USC 2017",
    ),
    "child_care_credit": Citation(
        id="us:statutes/26/21",
        url=_axiom_us_url("statute", "26", "21"),
        title="Child and dependent care credit",
        source="26 USC 21",
    ),
    "other_refundable_tax_credits": Citation(
        id="policyengine-us:variables/income_tax_refundable_credits",
        url="https://github.com/PolicyEngine/policyengine-us",
        title="Federal refundable income tax credits",
        source="PolicyEngine-US variable",
    ),
}

TAX_CITATION_KEYS = (
    "federal_income_tax",
    "state_income_tax",
    "payroll_tax",
)


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
    """Map household result fields to the sources that support them."""
    benefit_keys = _benefit_keys(result)
    tax_keys = list(TAX_CITATION_KEYS)
    if _has_self_employment_tax(result):
        tax_keys.append("self_employment_tax")

    tax_citations = _citations_for_keys(tax_keys)
    benefit_citations = _citations_for_keys(benefit_keys)
    resource_citations = _dedupe_citations([*tax_citations, *benefit_citations])

    output_citations: dict[str, list[Citation]] = {
        "federal_income_tax": _citations_for_keys(["federal_income_tax"]),
        "state_income_tax": _citations_for_keys(["state_income_tax"]),
        "payroll_tax": _citations_for_keys(tax_keys[2:]),
        "total_taxes": tax_citations,
        "total_benefits": benefit_citations,
        "net_income": resource_citations,
        "effective_tax_rate": tax_citations,
        "marginal_tax_rate": tax_citations,
    }

    for benefit_key in benefit_keys:
        output_citations[f"benefits.{benefit_key}"] = _citations_for_keys([benefit_key])

    return {key: value for key, value in output_citations.items() if value}


def _benefit_keys(result: Any | None) -> list[str]:
    if result is None:
        return [
            "child_tax_credit",
            "eitc",
            "snap",
            "child_care_credit",
            "other_refundable_tax_credits",
        ]
    benefits = getattr(result, "benefits", {}) or {}
    keys = list(benefits.keys())
    tax_breakdown = getattr(result, "tax_breakdown", {}) or {}
    if tax_breakdown.get("child_tax_credit_total", 0) > 0:
        keys.append("child_tax_credit")
    if tax_breakdown.get("child_care_credit_total", 0) > 0:
        keys.append("child_care_credit")
    return sorted(set(keys))


def _has_self_employment_tax(result: Any | None) -> bool:
    if result is None:
        return True
    tax_breakdown = getattr(result, "tax_breakdown", {}) or {}
    payroll_tax = getattr(result, "payroll_tax", 0)
    fica = tax_breakdown.get("fica", payroll_tax)
    return payroll_tax > fica + 0.01


def _citations_for_keys(keys: list[str] | tuple[str, ...]) -> list[Citation]:
    return _dedupe_citations(
        HOUSEHOLD_CITATIONS[key] for key in keys if key in HOUSEHOLD_CITATIONS
    )


def _dedupe_citations(citations: Any) -> list[Citation]:
    seen: set[str] = set()
    deduped: list[Citation] = []
    for citation in citations:
        if citation.id in seen:
            continue
        seen.add(citation.id)
        deduped.append(citation)
    return deduped
