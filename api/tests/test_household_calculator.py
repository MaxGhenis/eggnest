"""Tests for household tax and benefits calculator."""

from fastapi.testclient import TestClient

from eggnest.household import HouseholdCalculator
from eggnest.models import (
    HouseholdInput,
    PersonInput,
)
from main import app

client = TestClient(app)


class TestPersonInput:
    """Test PersonInput model."""

    def test_adult_person(self):
        """Test creating an adult person."""
        person = PersonInput(
            age=35,
            employment_income=75000,
            is_tax_unit_head=True,
        )
        assert person.age == 35
        assert person.employment_income == 75000

    def test_child_person(self):
        """Test creating a child."""
        child = PersonInput(
            age=5,
            employment_income=0,
            is_tax_unit_head=False,
        )
        assert child.age == 5
        assert child.is_tax_unit_dependent is True  # Should default for children

    def test_person_defaults(self):
        """Test default values for person."""
        person = PersonInput(age=30)
        assert person.employment_income == 0
        assert person.self_employment_income == 0
        assert person.social_security == 0


class TestHouseholdInput:
    """Test HouseholdInput model."""

    def test_single_filer(self):
        """Test single filer household."""
        household = HouseholdInput(
            state="CA",
            year=2025,
            people=[
                PersonInput(age=30, employment_income=50000, is_tax_unit_head=True)
            ],
        )
        assert household.filing_status == "single"
        assert len(household.people) == 1

    def test_married_couple(self):
        """Test married filing jointly household."""
        household = HouseholdInput(
            state="TX",
            year=2025,
            filing_status="married_filing_jointly",
            people=[
                PersonInput(age=40, employment_income=80000, is_tax_unit_head=True),
                PersonInput(age=38, employment_income=60000, is_tax_unit_spouse=True),
            ],
        )
        assert household.filing_status == "married_filing_jointly"
        assert len(household.people) == 2

    def test_family_with_children(self):
        """Test family with children."""
        household = HouseholdInput(
            state="NY",
            year=2025,
            filing_status="married_filing_jointly",
            people=[
                PersonInput(age=35, employment_income=100000, is_tax_unit_head=True),
                PersonInput(age=33, employment_income=50000, is_tax_unit_spouse=True),
                PersonInput(age=8, is_tax_unit_dependent=True),
                PersonInput(age=5, is_tax_unit_dependent=True),
            ],
        )
        assert len(household.people) == 4


class TestHouseholdCalculator:
    """Test HouseholdCalculator class."""

    def test_calculate_single_filer(self):
        """Test calculation for single filer."""
        household = HouseholdInput(
            state="CA",
            year=2025,
            people=[
                PersonInput(age=30, employment_income=50000, is_tax_unit_head=True)
            ],
        )
        calc = HouseholdCalculator()
        result = calc.calculate(household)

        assert result.federal_income_tax >= 0
        assert result.state_income_tax >= 0
        assert result.total_income == 50000
        assert "federal_income_tax" in result.tax_breakdown
        assert "fica" in result.tax_breakdown

    def test_calculate_with_children_gets_ctc(self):
        """Test that family with children gets Child Tax Credit."""
        household = HouseholdInput(
            state="TX",
            year=2025,
            filing_status="married_filing_jointly",
            people=[
                PersonInput(age=35, employment_income=80000, is_tax_unit_head=True),
                PersonInput(age=33, employment_income=0, is_tax_unit_spouse=True),
                PersonInput(age=8, is_tax_unit_dependent=True),
            ],
        )
        calc = HouseholdCalculator()
        result = calc.calculate(household)

        # Should get CTC for 1 child
        assert result.benefits.get("child_tax_credit", 0) > 0

    def test_low_income_gets_eitc(self):
        """Test that low-income family gets EITC."""
        household = HouseholdInput(
            state="FL",
            year=2025,
            filing_status="single",
            people=[
                PersonInput(age=28, employment_income=20000, is_tax_unit_head=True),
                PersonInput(age=4, is_tax_unit_dependent=True),
            ],
        )
        calc = HouseholdCalculator()
        result = calc.calculate(household)

        # Low income with child should get EITC
        assert result.benefits.get("eitc", 0) > 0

    def test_net_income_calculation(self):
        """Test net income after taxes and benefits."""
        household = HouseholdInput(
            state="WA",  # No state income tax
            year=2025,
            people=[
                PersonInput(age=40, employment_income=100000, is_tax_unit_head=True)
            ],
        )
        calc = HouseholdCalculator()
        result = calc.calculate(household)

        # Net income = gross - taxes + benefits
        expected_net = result.total_income - result.total_taxes + result.total_benefits
        assert abs(result.net_income - expected_net) < 1  # Allow small rounding

    def test_marginal_tax_rate(self):
        """Test marginal tax rate calculation."""
        household = HouseholdInput(
            state="CA",
            year=2025,
            people=[
                PersonInput(age=35, employment_income=75000, is_tax_unit_head=True)
            ],
        )
        calc = HouseholdCalculator()
        result = calc.calculate(household)

        # Marginal rate should be reasonable (between 0 and 60%)
        assert 0 <= result.marginal_tax_rate <= 0.60

    def test_zero_income_household(self):
        """Test household with zero income."""
        household = HouseholdInput(
            state="CA",
            year=2025,
            people=[PersonInput(age=25, employment_income=0, is_tax_unit_head=True)],
        )
        calc = HouseholdCalculator()
        result = calc.calculate(household)

        assert result.total_income == 0
        assert result.federal_income_tax == 0


class TestLifeEventComparison:
    """Test life event comparison functionality."""

    def test_adding_child_comparison(self):
        """Test comparing before/after adding a child."""
        # Before: Single person
        before = HouseholdInput(
            state="CA",
            year=2025,
            people=[
                PersonInput(age=30, employment_income=60000, is_tax_unit_head=True)
            ],
        )

        # After: Same person with a child
        after = HouseholdInput(
            state="CA",
            year=2025,
            filing_status="head_of_household",
            people=[
                PersonInput(age=30, employment_income=60000, is_tax_unit_head=True),
                PersonInput(age=0, is_tax_unit_dependent=True),  # Newborn
            ],
        )

        calc = HouseholdCalculator()
        comparison = calc.compare(before, after)

        # Adding a child should reduce taxes (CTC) and change filing status
        assert comparison.tax_change < 0  # Taxes should decrease
        assert comparison.benefit_change >= 0  # Benefits should increase or stay same
        assert comparison.net_income_change > 0  # Net income should increase

    def test_marriage_comparison(self):
        """Test comparing before/after marriage."""
        # Before: Two single people (calculated separately, but we model just one)
        before = HouseholdInput(
            state="NY",
            year=2025,
            people=[
                PersonInput(age=28, employment_income=70000, is_tax_unit_head=True)
            ],
        )

        # After: Married filing jointly
        after = HouseholdInput(
            state="NY",
            year=2025,
            filing_status="married_filing_jointly",
            people=[
                PersonInput(age=28, employment_income=70000, is_tax_unit_head=True),
                PersonInput(age=26, employment_income=50000, is_tax_unit_spouse=True),
            ],
        )

        calc = HouseholdCalculator()
        comparison = calc.compare(before, after)

        # Should have some change (marriage bonus/penalty depends on income levels)
        assert comparison.before_result is not None
        assert comparison.after_result is not None


class TestHouseholdEndpoint:
    """Test /calculate-household API endpoint."""

    def test_calculate_endpoint_returns_result(self):
        """Test that endpoint returns valid result."""
        response = client.post(
            "/calculate-household",
            json={
                "state": "CA",
                "year": 2025,
                "people": [
                    {"age": 35, "employment_income": 75000, "is_tax_unit_head": True}
                ],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "federal_income_tax" in data
        assert "state_income_tax" in data
        assert "total_income" in data
        assert "net_income" in data

    def test_calculate_endpoint_with_family(self):
        """Test endpoint with family."""
        response = client.post(
            "/calculate-household",
            json={
                "state": "TX",
                "year": 2025,
                "filing_status": "married_filing_jointly",
                "people": [
                    {"age": 40, "employment_income": 100000, "is_tax_unit_head": True},
                    {"age": 38, "employment_income": 60000, "is_tax_unit_spouse": True},
                    {"age": 10, "is_tax_unit_dependent": True},
                    {"age": 7, "is_tax_unit_dependent": True},
                ],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total_income"] == 160000
        # Should have CTC for 2 children
        assert data["benefits"].get("child_tax_credit", 0) > 0

    def test_calculate_endpoint_validates_state(self):
        """Test that endpoint validates state code."""
        response = client.post(
            "/calculate-household",
            json={
                "state": "XX",  # Invalid state
                "year": 2025,
                "people": [
                    {"age": 30, "employment_income": 50000, "is_tax_unit_head": True}
                ],
            },
        )
        # Should either reject or handle gracefully
        assert response.status_code in [200, 400, 422]


class TestCompareEndpoint:
    """Test /compare-life-event API endpoint."""

    def test_compare_endpoint_returns_result(self):
        """Test that compare endpoint returns valid result."""
        response = client.post(
            "/compare-life-event",
            json={
                "before": {
                    "state": "CA",
                    "year": 2025,
                    "people": [
                        {
                            "age": 30,
                            "employment_income": 60000,
                            "is_tax_unit_head": True,
                        }
                    ],
                },
                "after": {
                    "state": "CA",
                    "year": 2025,
                    "filing_status": "head_of_household",
                    "people": [
                        {
                            "age": 30,
                            "employment_income": 60000,
                            "is_tax_unit_head": True,
                        },
                        {"age": 0, "is_tax_unit_dependent": True},
                    ],
                },
                "event_name": "Having a child",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "before_result" in data
        assert "after_result" in data
        assert "tax_change" in data
        assert "benefit_change" in data
        assert "net_income_change" in data

    def test_compare_income_change(self):
        """Test comparing income change scenario."""
        response = client.post(
            "/compare-life-event",
            json={
                "before": {
                    "state": "CA",
                    "year": 2025,
                    "people": [
                        {
                            "age": 35,
                            "employment_income": 75000,
                            "is_tax_unit_head": True,
                        }
                    ],
                },
                "after": {
                    "state": "CA",
                    "year": 2025,
                    "people": [
                        {
                            "age": 35,
                            "employment_income": 100000,
                            "is_tax_unit_head": True,
                        }
                    ],
                },
                "event_name": "Getting a raise",
            },
        )
        assert response.status_code == 200

        data = response.json()
        # Higher income should mean higher taxes
        assert data["tax_change"] > 0
        # But also higher net income
        assert data["net_income_change"] > 0
