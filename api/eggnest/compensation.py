"""Employer-side compensation and package analysis helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from policyengine_us import Simulation

from eggnest.household import HouseholdCalculator
from eggnest.models import (
    CompensationAnalysisInput,
    CompensationAnalysisResult,
    CompensationBenchmark,
    CompensationEmployeeProfile,
    CompensationEmployeeValue,
    CompensationEmployerCost,
    CompensationMarketPosition,
    CompensationPackageInput,
    CompensationPackageTotals,
    HouseholdInput,
    PersonInput,
)

DATA_PATH = Path(__file__).parent / "data" / "nyc_total_comp_breakdown.csv"
OPTIONAL_EMPLOYER_TAX_VARIABLES = (
    "employer_federal_unemployment_tax",
    "employer_unemployment_tax",
    "employer_state_payroll_tax",
    "employer_local_payroll_tax",
    "employer_futa",
)
AGGREGATE_EMPLOYER_TAX_VARIABLES = (
    "employer_payroll_tax",
    "employer_payroll_taxes",
)


@dataclass(slots=True)
class MarketBenchmark:
    benchmark_id: str
    role: str
    tier: str
    p25_total: float
    p50_total: float
    p75_total: float
    source: str


def _benchmark_id(role: str, tier: str) -> str:
    return f"{role}::{tier}"


@lru_cache(maxsize=1)
def load_market_benchmarks() -> dict[str, MarketBenchmark]:
    benchmarks: dict[str, MarketBenchmark] = {}
    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = row["role"]
            tier = row["tier"]
            benchmark = MarketBenchmark(
                benchmark_id=_benchmark_id(role, tier),
                role=role,
                tier=tier,
                p25_total=float(row["total_comp_p25"]),
                p50_total=float(row["total_comp_p50"]),
                p75_total=float(row["total_comp_p75"]),
                source=row["source"],
            )
            benchmarks[benchmark.benchmark_id] = benchmark
    return benchmarks


def list_market_benchmarks() -> list[CompensationBenchmark]:
    return [
        CompensationBenchmark(
            id=benchmark.benchmark_id,
            role=benchmark.role,
            tier=benchmark.tier,
            label=f"{benchmark.role} — {benchmark.tier}",
            source=benchmark.source,
            market_p25_total=benchmark.p25_total,
            market_p50_total=benchmark.p50_total,
            market_p75_total=benchmark.p75_total,
        )
        for benchmark in sorted(
            load_market_benchmarks().values(),
            key=lambda b: (b.role, b.tier),
        )
    ]


def estimate_percentile_from_anchors(
    value: float, p25: float, p50: float, p75: float
) -> float:
    """Estimate percentile from p25/p50/p75 anchors."""
    if value <= p25:
        if p25 > 0:
            return max(0.0, 0.25 * (value / p25))
        return 0.0
    if value <= p50:
        if p50 == p25:
            return 0.5
        return 0.25 + 0.25 * ((value - p25) / (p50 - p25))
    if value <= p75:
        if p75 == p50:
            return 0.75
        return 0.5 + 0.25 * ((value - p50) / (p75 - p50))
    spread = p75 - p50
    if spread > 0:
        return min(0.99, 0.75 + 0.25 * ((value - p75) / spread))
    return 0.99


def percentile_label(percentile: float) -> str:
    return f"P{round(percentile * 100)}"


def _employer_retirement_amount(package: CompensationPackageInput) -> float:
    if package.employer_retirement_amount is not None:
        return package.employer_retirement_amount
    amount = package.salary * package.employer_retirement_rate
    if package.employer_retirement_cap is not None:
        amount = min(amount, package.employer_retirement_cap)
    return amount


def _cash_wages(package: CompensationPackageInput) -> float:
    wages = package.salary + package.annual_bonus
    if package.taxable_equity_treatment == "w2":
        wages += package.annual_equity
    return wages


def _build_household(
    package: CompensationPackageInput,
    profile: CompensationEmployeeProfile,
) -> HouseholdInput:
    people: list[PersonInput] = [
        PersonInput(
            age=profile.age,
            employment_income=_cash_wages(package),
            capital_gains=(
                package.annual_equity
                if package.taxable_equity_treatment == "capital_gains"
                else 0
            ),
            is_tax_unit_head=True,
        )
    ]

    if profile.filing_status == "married_filing_jointly":
        people.append(
            PersonInput(
                age=profile.spouse_age,
                employment_income=profile.spouse_employment_income,
                is_tax_unit_spouse=True,
            )
        )

    for _ in range(profile.children):
        people.append(PersonInput(age=profile.child_age))

    return HouseholdInput(
        state=profile.state,
        year=profile.year,
        filing_status=profile.filing_status,
        people=people,
    )


def _build_employer_tax_household(
    package: CompensationPackageInput,
    profile: CompensationEmployeeProfile,
) -> HouseholdInput:
    return HouseholdInput(
        state=profile.state,
        year=profile.year,
        filing_status="single",
        people=[
            PersonInput(
                age=profile.age,
                employment_income=_cash_wages(package),
                is_tax_unit_head=True,
            )
        ],
    )


def _employer_payroll_taxes(
    package: CompensationPackageInput,
    profile: CompensationEmployeeProfile,
) -> dict[str, float | dict[str, float] | list[str]]:
    household = _build_employer_tax_household(package, profile)
    calc = HouseholdCalculator()
    situation = calc._build_situation(household)
    sim = Simulation(situation=situation)
    year = household.year
    employer_social_security_tax = float(
        sim.calculate("employer_social_security_tax", year).sum()
    )
    employer_medicare_tax = float(sim.calculate("employer_medicare_tax", year).sum())

    aggregate_total = None
    aggregate_variable_used = None
    for variable in AGGREGATE_EMPLOYER_TAX_VARIABLES:
        try:
            aggregate_total = float(sim.calculate(variable, year).sum())
            aggregate_variable_used = variable
            break
        except ValueError:
            continue

    tax_components = {
        "employer_social_security_tax": employer_social_security_tax,
        "employer_medicare_tax": employer_medicare_tax,
    }
    for variable in OPTIONAL_EMPLOYER_TAX_VARIABLES:
        try:
            value = float(sim.calculate(variable, year).sum())
        except ValueError:
            continue
        tax_components[variable] = value

    employer_payroll_taxes = (
        aggregate_total if aggregate_total is not None else sum(tax_components.values())
    )
    variables_used = list(tax_components.keys())
    if aggregate_variable_used is not None:
        variables_used = [aggregate_variable_used, *variables_used]

    return {
        "employer_social_security_tax": employer_social_security_tax,
        "employer_medicare_tax": employer_medicare_tax,
        "employer_additional_payroll_taxes": sum(
            value
            for variable, value in tax_components.items()
            if variable not in {"employer_social_security_tax", "employer_medicare_tax"}
        ),
        "employer_payroll_taxes": employer_payroll_taxes,
        "employer_payroll_tax_components": tax_components,
        "employer_payroll_tax_variables_used": variables_used,
    }


def analyze_package(
    package: CompensationPackageInput,
    employee_profile: CompensationEmployeeProfile,
) -> CompensationAnalysisResult:
    benchmarks = load_market_benchmarks()
    benchmark = benchmarks.get(package.benchmark_id)
    if benchmark is None:
        raise KeyError(f"Unknown benchmark_id '{package.benchmark_id}'")

    employer_retirement = _employer_retirement_amount(package)
    guaranteed_total = package.salary + employer_retirement
    upside_total = guaranteed_total + package.annual_bonus + package.annual_equity

    guaranteed_percentile = estimate_percentile_from_anchors(
        guaranteed_total, benchmark.p25_total, benchmark.p50_total, benchmark.p75_total
    )
    upside_percentile = estimate_percentile_from_anchors(
        upside_total, benchmark.p25_total, benchmark.p50_total, benchmark.p75_total
    )

    household = _build_household(package, employee_profile)
    household_result = HouseholdCalculator().calculate(household)
    employer_tax_breakdown = _employer_payroll_taxes(package, employee_profile)

    benefits_value = (
        employer_retirement
        + package.employer_health_premiums
        + package.other_employer_costs
    )

    return CompensationAnalysisResult(
        package=package,
        benchmark=CompensationBenchmark(
            id=benchmark.benchmark_id,
            role=benchmark.role,
            tier=benchmark.tier,
            label=f"{benchmark.role} — {benchmark.tier}",
            source=benchmark.source,
            market_p25_total=benchmark.p25_total,
            market_p50_total=benchmark.p50_total,
            market_p75_total=benchmark.p75_total,
        ),
        totals=CompensationPackageTotals(
            guaranteed_total=guaranteed_total,
            upside_total=upside_total,
            employer_retirement=employer_retirement,
            taxable_wages=_cash_wages(package),
        ),
        market_position=CompensationMarketPosition(
            guaranteed_percentile=guaranteed_percentile,
            upside_percentile=upside_percentile,
            guaranteed_percentile_label=percentile_label(guaranteed_percentile),
            upside_percentile_label=percentile_label(upside_percentile),
            market_p25_total=benchmark.p25_total,
            market_p50_total=benchmark.p50_total,
            market_p75_total=benchmark.p75_total,
        ),
        employer_cost=CompensationEmployerCost(
            salary=package.salary,
            annual_bonus=package.annual_bonus,
            annual_equity=package.annual_equity,
            employer_retirement=employer_retirement,
            employer_health_premiums=package.employer_health_premiums,
            other_employer_costs=package.other_employer_costs,
            employer_social_security_tax=float(
                employer_tax_breakdown["employer_social_security_tax"]
            ),
            employer_medicare_tax=float(
                employer_tax_breakdown["employer_medicare_tax"]
            ),
            employer_additional_payroll_taxes=float(
                employer_tax_breakdown["employer_additional_payroll_taxes"]
            ),
            employer_payroll_tax_components=dict(
                employer_tax_breakdown["employer_payroll_tax_components"]
            ),
            employer_payroll_tax_variables_used=list(
                employer_tax_breakdown["employer_payroll_tax_variables_used"]
            ),
            employer_payroll_taxes=float(employer_tax_breakdown["employer_payroll_taxes"]),
            total_cost=(
                package.salary
                + package.annual_bonus
                + package.annual_equity
                + employer_retirement
                + package.employer_health_premiums
                + package.other_employer_costs
                + float(employer_tax_breakdown["employer_payroll_taxes"])
            ),
        ),
        employee_value=CompensationEmployeeValue(
            gross_income=household_result.total_income,
            federal_income_tax=household_result.federal_income_tax,
            state_income_tax=household_result.state_income_tax,
            payroll_tax=household_result.payroll_tax,
            total_taxes=household_result.total_taxes,
            modeled_public_benefits=household_result.total_benefits,
            cash_after_tax=household_result.net_income,
            employer_retirement=employer_retirement,
            employer_health_premiums=package.employer_health_premiums,
            other_benefits_value=package.other_employer_costs,
            net_resources_total=household_result.net_income + benefits_value,
            effective_tax_rate=household_result.effective_tax_rate,
            marginal_tax_rate=household_result.marginal_tax_rate,
        ),
    )


def analyze_compensation(
    input_data: CompensationAnalysisInput,
) -> list[CompensationAnalysisResult]:
    return [
        analyze_package(package, input_data.employee_profile)
        for package in input_data.packages
    ]
