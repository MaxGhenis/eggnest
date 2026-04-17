"""Tests for employer-side compensation analysis."""

from fastapi.testclient import TestClient
import pytest

from eggnest.compensation import analyze_package
from eggnest.models import (
    CompensationEmployeeProfile,
    CompensationPackageInput,
)
from main import app

client = TestClient(app)


def make_package(**overrides) -> CompensationPackageInput:
    payload = {
        "name": "Senior ML package",
        "benchmark_id": "Senior ML/AI Engineer::Nonprofit/mission",
        "salary": 260_000,
        "annual_bonus": 15_000,
        "annual_equity": 0,
        "employer_retirement_rate": 0.25,
        "employer_retirement_cap": 47_500,
        "employer_health_premiums": 24_000,
        "other_employer_costs": 8_000,
    }
    payload.update(overrides)
    return CompensationPackageInput(**payload)


def make_profile(**overrides) -> CompensationEmployeeProfile:
    payload = {
        "state": "NY",
        "year": 2026,
        "filing_status": "single",
        "age": 35,
    }
    payload.update(overrides)
    return CompensationEmployeeProfile(**payload)


def test_compensation_benchmarks_endpoint_returns_rows():
    response = client.get("/compensation/benchmarks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["id"]
    assert data[0]["market_p50_total"] > 0


def test_employer_health_costs_do_not_change_market_percentile():
    base = analyze_package(make_package(), make_profile())
    richer_benefits = analyze_package(
        make_package(employer_health_premiums=60_000, other_employer_costs=25_000),
        make_profile(),
    )

    assert (
        base.market_position.guaranteed_percentile
        == richer_benefits.market_position.guaranteed_percentile
    )
    assert base.employer_cost.total_cost < richer_benefits.employer_cost.total_cost


def test_spouse_income_does_not_change_employer_payroll_tax_cost():
    single = analyze_package(make_package(), make_profile())
    married = analyze_package(
        make_package(),
        make_profile(
            filing_status="married_filing_jointly",
            spouse_age=34,
            spouse_employment_income=300_000,
        ),
    )

    assert single.employer_cost.employer_payroll_taxes == married.employer_cost.employer_payroll_taxes
    assert single.employee_value.net_resources_total != married.employee_value.net_resources_total


def test_employer_payroll_tax_components_are_exposed():
    result = analyze_package(make_package(), make_profile())

    assert result.employer_cost.employer_payroll_tax_components[
        "employer_social_security_tax"
    ] == result.employer_cost.employer_social_security_tax
    assert result.employer_cost.employer_payroll_tax_components[
        "employer_medicare_tax"
    ] == result.employer_cost.employer_medicare_tax
    assert result.employer_cost.employer_additional_payroll_taxes == pytest.approx(
        result.employer_cost.employer_payroll_taxes
        - result.employer_cost.employer_social_security_tax
        - result.employer_cost.employer_medicare_tax
    )
    assert "employer_social_security_tax" in result.employer_cost.employer_payroll_tax_variables_used


def test_compensation_analyze_endpoint_returns_market_cost_and_employee_value():
    response = client.post(
        "/compensation/analyze",
        json={
            "employee_profile": {
                "state": "CA",
                "year": 2026,
                "filing_status": "single",
                "age": 35,
            },
            "packages": [
                {
                    "name": "CTO",
                    "benchmark_id": "CTO (mid-stage startup)::Nonprofit/mission",
                    "salary": 390000,
                    "annual_bonus": 50000,
                    "annual_equity": 0,
                    "employer_retirement_rate": 0.25,
                    "employer_retirement_cap": 47500,
                    "employer_health_premiums": 24000,
                    "other_employer_costs": 12000,
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    result = data[0]
    assert result["market_position"]["guaranteed_percentile_label"].startswith("P")
    assert result["employer_cost"]["total_cost"] > result["package"]["salary"]
    assert result["employee_value"]["net_resources_total"] > 0
